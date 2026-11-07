"""Worker de envío de notificaciones (C-08 D-2/D-3/D-4/D-8/D-10/D-13).

`run_once` procesa de a una `Notificacion pendiente` vencida: claim con
`FOR UPDATE OF n SKIP LOCKED`, envío por el `MailSender` inyectado y commit
por fila. At-least-once, single-process; sin Redis (PB-03).
"""

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.notificaciones.payload import (
    PayloadIncompleto,
    motivo_payload_incompleto,
    motivo_smtp,
    motivo_turno_cancelado,
    validar_payload,
)
from app.modules.notificaciones.sender import MailSender
from app.modules.notificaciones.templates import render

logger = logging.getLogger(__name__)

ESTADOS_TURNO_ACTIVOS = ("reservado", "confirmado")

# D-3: defensa no bloqueante contra ciclos solapados (además de
# `max_instances=1` en el scheduler). El ciclo es single-process.
_LOCK = threading.Lock()


@dataclass
class Resumen:
    """Contadores de un ciclo (D-13 paso 7)."""

    enviadas: int = 0
    reintentos: int = 0
    fallidas: int = 0
    descartadas: int = 0
    payload_invalidos: int = 0


_SQL_CLAIM = text(
    """
    SELECT n.id,
           n.turno_id,
           n.tipo,
           n.intentos,
           n.payload,
           t.estado AS turno_estado
    FROM notificacion AS n
    JOIN turno AS t ON t.id = n.turno_id
    WHERE n.estado = 'pendiente'
      AND n.canal = 'mail'
      AND n.payload ? 'enviar_en'
      AND pg_input_is_valid(n.payload->>'enviar_en', 'timestamptz')
      AND (n.payload->>'enviar_en')::timestamptz <= :now
    ORDER BY (n.payload->>'enviar_en')::timestamptz, n.id
    FOR UPDATE OF n SKIP LOCKED
    LIMIT 1
    """
)

_SQL_SANEAMIENTO = text(
    """
    WITH lote AS (
        SELECT n.id
        FROM notificacion AS n
        WHERE n.estado = 'pendiente'
          AND n.canal = 'mail'
          AND (
              n.payload->>'enviar_en' IS NULL
              OR NOT pg_input_is_valid(n.payload->>'enviar_en', 'timestamptz')
          )
        ORDER BY n.id
        FOR UPDATE OF n SKIP LOCKED
        LIMIT :batch
    )
    UPDATE notificacion AS n
    SET estado = 'fallida', error = :motivo
    FROM lote
    WHERE n.id = lote.id
    RETURNING n.id, n.turno_id, n.tipo, n.intentos
    """
)

_SQL_ENVIADA = text(
    """
    UPDATE notificacion
    SET estado = 'enviada', enviada_at = :now, error = NULL
    WHERE id = :id
    """
)

_SQL_REINTENTO = text(
    """
    UPDATE notificacion
    SET estado = 'pendiente',
        intentos = :intentos,
        error = :error,
        payload = jsonb_set(
            payload,
            '{enviar_en}',
            to_jsonb(CAST(:nuevo_enviar_en AS text)),
            true
        )
    WHERE id = :id
    """
)

_SQL_FALLIDA = text(
    """
    UPDATE notificacion
    SET estado = 'fallida', intentos = :intentos, error = :error
    WHERE id = :id
    """
)

_SQL_DESCARTE = text(
    """
    UPDATE notificacion
    SET estado = 'fallida', error = :error
    WHERE id = :id
    """
)


@contextmanager
def _abrir(session_factory: Session | Callable[[], Session]) -> Iterator[Session]:
    """Acepta una sesión (tests) o una fábrica (producción, cierra al final)."""
    if isinstance(session_factory, Session):
        yield session_factory
        return
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _texto(valor) -> str:
    return str(getattr(valor, "value", valor))


def _enmascarar(email: str) -> str:
    """D-10: destinatario enmascarado (`p***@dominio`)."""
    local, sep, dominio = str(email).partition("@")
    if not sep:
        return "***"
    return f"{local[:1]}***@{dominio}"


def _log(
    evento: str,
    fila,
    resultado: str,
    *,
    destinatario: str | None = None,
    motivo: str | None = None,
    intentos: int | None = None,
    nivel: int = logging.INFO,
) -> None:
    """Log estructurado por resultado, sin secretos ni PII extra (D-10)."""
    try:
        logger.log(
            nivel,
            "%s notificacion_id=%s turno_id=%s tipo=%s intentos=%s "
            "resultado=%s destinatario=%s motivo=%s",
            evento,
            fila.id,
            fila.turno_id,
            _texto(fila.tipo),
            fila.intentos if intentos is None else intentos,
            resultado,
            _enmascarar(destinatario) if destinatario else "-",
            motivo or "-",
        )
    except Exception:  # pragma: no cover - el log nunca corta el lote
        pass


def _registrar_fallo(db: Session, fila, now: datetime, motivo: str) -> str:
    """D-4: `intentos++`, backoff `now + 5×intentos` o `fallida` al 3.º."""
    intentos = int(fila.intentos or 0) + 1
    if intentos >= 3:
        db.execute(
            _SQL_FALLIDA,
            {"id": fila.id, "intentos": intentos, "error": motivo},
        )
        db.commit()
        _log(
            "notificacion_fallida",
            fila,
            "fallida",
            motivo=motivo,
            intentos=intentos,
            nivel=logging.WARNING,
        )
        return "fallida"
    nuevo_enviar_en = (now + timedelta(minutes=5 * intentos)).astimezone(UTC)
    db.execute(
        _SQL_REINTENTO,
        {
            "id": fila.id,
            "intentos": intentos,
            "error": motivo,
            "nuevo_enviar_en": nuevo_enviar_en.isoformat(),
        },
    )
    db.commit()
    _log(
        "notificacion_reintento",
        fila,
        "reintento",
        motivo=motivo,
        intentos=intentos,
        nivel=logging.WARNING,
    )
    return "reintento"


def _procesar_fila(db: Session, fila, sender: MailSender, now: datetime) -> str:
    """D-13 pasos 3–6 para una fila ya bloqueada."""
    try:
        payload = validar_payload(fila.payload)
    except PayloadIncompleto as exc:
        motivo = motivo_payload_incompleto(exc.detalle)
        db.execute(_SQL_DESCARTE, {"id": fila.id, "error": motivo})
        db.commit()
        _log(
            "notificacion_payload_invalido",
            fila,
            "payload_invalido",
            motivo=motivo,
            nivel=logging.WARNING,
        )
        return "payload_invalido"

    estado_turno = _texto(fila.turno_estado)
    if payload.tipo != "cancelacion" and estado_turno not in ESTADOS_TURNO_ACTIVOS:
        motivo = motivo_turno_cancelado(estado_turno)
        db.execute(_SQL_DESCARTE, {"id": fila.id, "error": motivo})
        db.commit()
        _log(
            "notificacion_descartada",
            fila,
            "descartada",
            motivo=motivo,
            nivel=logging.WARNING,
        )
        return "descartada"

    asunto, cuerpo = render(payload.tipo, payload)
    try:
        sender.send(
            asunto=asunto, cuerpo=cuerpo, destinatario=payload.paciente_email
        )
    except Exception as exc:
        return _registrar_fallo(db, fila, now, motivo_smtp(str(exc)))

    db.execute(_SQL_ENVIADA, {"id": fila.id, "now": now})
    db.commit()
    _log(
        "notificacion_enviada",
        fila,
        "enviada",
        destinatario=payload.paciente_email,
    )
    return "enviada"


def _saneamiento(db: Session, now: datetime, batch_size: int, resumen: Resumen) -> None:
    """D-2/D-13: `enviar_en` ausente/inválido → `fallida`/`payload_incompleto`."""
    motivo = motivo_payload_incompleto("enviar_en ausente o inválido")
    filas = db.execute(
        _SQL_SANEAMIENTO, {"batch": batch_size, "motivo": motivo}
    ).all()
    if not filas:
        return
    db.commit()
    for fila in filas:
        resumen.payload_invalidos += 1
        _log(
            "notificacion_payload_invalido",
            fila,
            "payload_invalido",
            motivo=motivo,
            nivel=logging.WARNING,
        )


def run_once(
    session_factory: Session | Callable[[], Session],
    sender: MailSender,
    *,
    now: datetime | None = None,
    batch_size: int | None = None,
) -> Resumen:
    """Ejecuta un ciclo completo del worker (D-13).

    Si otro ciclo está en curso, el disparo se omite y se loguea (D-3).
    """
    if not _LOCK.acquire(blocking=False):
        logger.warning(
            "notificacion_ciclo_solapado resultado=omitido "
            "motivo=ciclo_en_curso"
        )
        return Resumen()
    try:
        momento = (now or datetime.now(UTC)).astimezone(UTC)
        limite = batch_size or get_settings().NOTIF_WORKER_BATCH_SIZE
        resumen = Resumen()

        with _abrir(session_factory) as db:
            _saneamiento(db, momento, limite, resumen)

            for _ in range(limite):
                fila = db.execute(_SQL_CLAIM, {"now": momento}).first()
                if fila is None:
                    break
                try:
                    resultado = _procesar_fila(db, fila, sender, momento)
                except Exception as exc:  # aislamiento por fila (D-13)
                    db.rollback()
                    try:
                        resultado = _registrar_fallo(
                            db, fila, momento, motivo_smtp(str(exc))
                        )
                    except Exception:  # pragma: no cover - DB rota: cortar el ciclo
                        db.rollback()
                        _log(
                            "notificacion_fallida",
                            fila,
                            "fallida",
                            motivo=motivo_smtp(str(exc)),
                            nivel=logging.ERROR,
                        )
                        break
                _contar(resumen, resultado)

        return resumen
    finally:
        _LOCK.release()


def _contar(resumen: Resumen, resultado: str) -> None:
    if resultado == "enviada":
        resumen.enviadas += 1
    elif resultado == "reintento":
        resumen.reintentos += 1
    elif resultado == "fallida":
        resumen.fallidas += 1
    elif resultado == "descartada":
        resumen.descartadas += 1
    elif resultado == "payload_invalido":
        resumen.payload_invalidos += 1

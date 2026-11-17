"""Consulta keyset del panel staff de fallidas (C-08 D-9).

Columnas explícitas, cursor opaco `base64url(inicio|id)` y `LIMIT limit+1`
para calcular `next_cursor`. Sin `OFFSET` (duro 7).
"""

import base64
import binascii
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

_SQL_BASE = text(
    """
    SELECT n.id,
           n.turno_id,
           n.tipo,
           n.intentos,
           n.error,
           n.payload->>'enviar_en' AS enviar_en,
           n.payload->>'paciente_nombre' AS paciente_nombre,
           n.payload->>'paciente_email' AS paciente_email,
           t.inicio,
           t.fin
    FROM notificacion AS n
    JOIN turno AS t ON t.id = n.turno_id
    WHERE n.estado = 'fallida'
      AND n.canal = 'mail'
      AND (n.error IS NULL OR n.error NOT LIKE 'turno_cancelado:%'
           AND n.error NOT LIKE 'turno_reprogramado:%')
    ORDER BY t.inicio DESC, n.id DESC
    LIMIT :limite
    """
)

_SQL_CURSOR = text(
    """
    SELECT n.id,
           n.turno_id,
           n.tipo,
           n.intentos,
           n.error,
           n.payload->>'enviar_en' AS enviar_en,
           n.payload->>'paciente_nombre' AS paciente_nombre,
           n.payload->>'paciente_email' AS paciente_email,
           t.inicio,
           t.fin
    FROM notificacion AS n
    JOIN turno AS t ON t.id = n.turno_id
    WHERE n.estado = 'fallida'
      AND n.canal = 'mail'
      AND (n.error IS NULL OR n.error NOT LIKE 'turno_cancelado:%'
           AND n.error NOT LIKE 'turno_reprogramado:%')
      AND (t.inicio, n.id) < (
          CAST(:cursor_inicio AS timestamptz),
          CAST(:cursor_id AS uuid)
      )
    ORDER BY t.inicio DESC, n.id DESC
    LIMIT :limite
    """
)


class CursorInvalido(Exception):
    """El cursor no decodifica o no representa `(inicio, id)` (D-9)."""


def codificar_cursor(inicio: datetime, notificacion_id: UUID) -> str:
    """Cursor opaco `base64url(inicio_iso|id)` sin padding."""
    crudo = f"{inicio.astimezone(UTC).isoformat()}|{notificacion_id}"
    return base64.urlsafe_b64encode(crudo.encode("utf-8")).decode().rstrip("=")


def decodificar_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Inverso de `codificar_cursor`; cualquier anomalía → `CursorInvalido`."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        crudo = base64.b64decode(padded, altchars=b"-_", validate=True).decode("utf-8")
        inicio_texto, separador, id_texto = crudo.partition("|")
        if not separador or not inicio_texto or not id_texto:
            raise ValueError("formato inesperado")
        inicio = datetime.fromisoformat(inicio_texto)
        if inicio.tzinfo is None or inicio.utcoffset() is None:
            raise ValueError("inicio sin zona horaria")
        return inicio.astimezone(UTC), UUID(id_texto)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise CursorInvalido("cursor inválido") from None


def _item(fila) -> dict:
    return {
        "id": fila.id,
        "turno_id": fila.turno_id,
        "tipo": fila.tipo,
        "intentos": fila.intentos,
        "error": fila.error,
        "enviar_en": fila.enviar_en,
        "paciente_nombre": fila.paciente_nombre,
        "paciente_email": fila.paciente_email,
        "inicio": fila.inicio,
        "fin": fila.fin,
    }


def listar_fallidas(
    db: Session,
    *,
    limit: int,
    cursor: str | None,
) -> dict:
    """Devuelve `{items, next_cursor}` con keyset por `(t.inicio, n.id)`."""
    parametros: dict = {"limite": limit + 1}
    sentencia = _SQL_BASE
    if cursor is not None:
        cursor_inicio, cursor_id = decodificar_cursor(cursor)
        parametros["cursor_inicio"] = cursor_inicio
        parametros["cursor_id"] = cursor_id
        sentencia = _SQL_CURSOR

    filas = db.execute(sentencia, parametros).all()
    visibles = filas[:limit]
    next_cursor = (
        codificar_cursor(visibles[-1].inicio, visibles[-1].id)
        if len(filas) > limit
        else None
    )
    return {
        "items": [_item(fila) for fila in visibles],
        "next_cursor": next_cursor,
    }

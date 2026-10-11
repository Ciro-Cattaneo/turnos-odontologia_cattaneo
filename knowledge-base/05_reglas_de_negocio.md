# Reglas de Negocio

Cada regla tiene código único para trazabilidad (US ↔ RN).

## Dominio: Turnos (RN-TU)

- **RN-TU-01**: No se puede reservar sin nombre + DNI + teléfono + obra social + mail (los cinco obligatorios). Mail con formato válido, sino 400 en ese campo. Toda reserva tiene mail: confirmación + recordatorios siempre encolados. — Discovery + GATE 2026-10-11 PB-02 (mail OBLIGATORIO).
- **RN-TU-02**: Duración default 30 minutos; recepción/admin puede personalizarla por turno y por profesional (`duracion_default_min`). — Discovery.
- **RN-TU-03**: Un profesional no puede tener dos turnos activos (`reservado`, `confirmado`) superpuestos. Se garantiza en transacción (SELECT FOR UPDATE del slot o constraint de exclusión Postgres). Intentar reservar un slot ocupado → 409 con slots alternativos del mismo día. — Discovery.
- **RN-TU-04**: No se puede cancelar un turno (paciente) con menos de 3 horas de anticipación al `inicio`. Recepción puede forzar la cancelación <3h, quedando registrada en `AuditoriaTurno` con actor y motivo. — Discovery.
- **RN-TU-05**: Los slots ofrecidos se computan como ventanas de `Disponibilidad` − `Bloqueos` − turnos activos. Si recepción no mantiene disponibilidades, el sistema muestra horarios falsos (riesgo principal de Discovery): la UI de recepción debe evidenciar "última actualización" por profesional.
- **RN-TU-06**: Reserva sin login en v1: la identidad del paciente por turno = `token_cancelacion` (única credencial, enviada por mail). Sin token no se puede ver/cancelar el turno. Sin UI "mis turnos" por DNI+teléfono. — GATE 2026-10-11 PB-01 (SOLO token).
- **RN-TU-07**: Estados permitidos: `reservado → confirmado → atendido | ausente`; `reservado|confirmado → cancelado`. Solo staff mueve a `confirmado/atendido/ausente`. Transiciones inválidas → 422.

## Dominio: Disponibilidad (RN-AG)

- **RN-AG-01**: Ventanas semanales recurrentes por profesional (`dia_semana`, `hora_desde/hasta`); excepciones vía `Bloqueo` con motivo. Sin ventana no hay slots.
- **RN-AG-02**: Granularidad de slots = duración del turno (default 30'). Si un profesional tiene `duracion_default_min=45`, sus slots son de 45'.
- **RN-AG-03**: Solo recepción/admin edita disponibilidades y bloqueos; odontólogo solo lectura de la propia.

## Dominio: Notificaciones (RN-NO)

- **RN-NO-01**: v1 solo mail. Al reservar se encola `confirmacion` inmediata SIEMPRE (toda reserva tiene mail — PB-02); worker envía `recordatorio_24h` y `recordatorio_2h` (si el turno se creó con esa anticipación). Sin fallback "sin mail".
- **RN-NO-02**: Envío asincrónico con reintentos (3 intentos, backoff). Tras 3 fallos → `fallida` + visible en panel recepción (no bloquea la reserva).
- **RN-NO-03**: WhatsApp queda fuera de v1. El `canal` es enum extensible; agregar WA post-v1 no cambia el contrato de encolado, solo suma un sender.

## Dominio: Pacientes y OS (RN-PA)

- **RN-PA-01**: Obra social = campo de texto obligatorio en v1, sin validación contra padrón. (El mercado — ClinIA/DoctorYa — valida; v1 acepta la deuda conscientemente por costo. Ver 10.)
- **RN-PA-02**: `dni` único por paciente; el teléfono es mutable (un paciente puede cambiar de número sin duplicarse).

## Dominio: Auth y auditoría (RN-AU)

- **RN-AU-01**: RBAC simple (paciente-público / odontólogo / recepción / admin). Sin ABAC ni permisos por recurso en v1.
- **RN-AU-02**: Toda mutación staff sobre turnos (crear/editar/cancelar/forzar/reprogramar) escribe `AuditoriaTurno` append-only con actor y timestamp.
- **RN-AU-03**: Rate-limit en endpoints públicos (`POST /api/turnos`, `GET /api/disponibilidad`) para evitar scraping/abuso de slots.

## Excepciones globales

- Todo horario es `America/Argentina/Buenos_Aires`; se persiste UTC y se muestra local. Sin soporte multi-zona en v1.
- Borrado: turnos cancelados se conservan (estado, no DELETE físico) para reportes/ausentismo. Pacientes: HÍBRIDO (GATE 2026-10-11 PB-04) — soft-delete default (`activo=false`, UI dice "desactivar"); DELETE físico permitido SOLO cuando el paciente tiene cero turnos; pedidos Ley 25.326 se resuelven con procedimiento manual documentado de anonimización (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos conservados como estadística; sin UI v1). Nunca hard-delete con turnos asociados.

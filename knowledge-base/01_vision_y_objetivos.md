# Visión y Objetivos

## Propósito del sistema

Eliminar las dobles reservas y el tiempo perdido confirmando turnos manualmente en el consultorio odontológico Cattaneo (AR), reemplazando la coordinación por WhatsApp/papel/planilla con una agenda digital única, multi-profesional desde el día 1, reservable online y administrable por recepción.

El diferencial a largo plazo es ocupar la intersección vacía del mercado: odontología pura + administración argentina (obras sociales, ARCA, Mercado Pago). v1 no la ocupa todavía: construye el flujo base de turnos a costo mínimo, dejando puerta abierta a WA/MP sin sobrediseñar (ver Fuera de alcance).

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|-------|--------------------|-----------------------|
| Paciente | Ver horarios libres y reservar/cancelar sin llamar ni escribir | Recibir recordatorio por mail; cancelar con ≥3h sin fricción desde el celular |
| Odontólogo/a | Ver sus turnos agendados (día/semana) para organizar su jornada | Distinguir estados (reservado/confirmado/cancelado/atendido); pedir duraciones distintas por prestación |
| Recepción/Admin | CRUD completo de turnos y validación de datos del paciente (DNI/tel/OS) | Mantener disponibilidades actualizadas; configurar duración default y excepciones; ver ocupación básica |

## Alcance v1

- Gestión de recepción: crear/editar/borrar/validar turnos (CRUD completo).
- Agenda por profesional con vista diaria y semanal, multi-profesional día 1.
- Reserva online por paciente con nombre + DNI + teléfono + obra social + mail obligatorios (los 5 — PB-02), sin login (identidad por turno = `token_cancelacion` — PB-01).
- Cancelación con anticipación mínima de 3 horas (paciente y recepción; recepción puede forzar con auditoría — ver RN-TU-04).
- Duración default 30 minutos, personalizable por el personal (por turno y por profesional).
- Recordatorios automáticos por mail (v1 confirmado) vía workers/cola.
- Frontend web responsive mobile-first (no app nativa).
- Roles y permisos mínimos: paciente (público) / odontólogo / recepción-admin.
- Single tenant inicial: un consultorio (Cattaneo).

## Fuera de alcance (explícitamente post-v1)

- WhatsApp (recordatorios, confirmación con respuesta, bot de reserva) — post-v1.
- Seña / cobro anticipado por Mercado Pago y política de no-show con pago — post-v1.
- Lista de espera con oferta automática de huecos — post-v1.
- Historia clínica / ficha vinculada / odontograma / presupuestos — post-v1.
- Validación contra padrón de obras sociales (PUCO/RENAPER) — v1 solo campo obligatorio; validación real post-v1.
- Facturación ARCA, liquidaciones OS, multi-sucursal, API pública, Google Calendar — post-v1.
- App nativa iOS/Android — nunca en roadmap actual; mobile-first = web responsive.

## Métricas de éxito (v1)

- Cero dobles reservas registradas por solapamiento (RN-TU-03 = 0 violaciones).
- ≥80% de reservas online originadas desde móvil (valida mobile-first).
- Tasa de ausentismo con recordatorio mail vs. línea base manual (aunque se espera mejora parcial; el salto real llega con WA post-v1).
- Tiempo de confirmación manual por turno → cercano a 0 para turnos online.
- Costo infra mensual dentro del piso del segmento chico (objetivo: comparable o menor a DarTurnos ~$3.300/mes + hosting barato; ver 09_decisiones_y_supuestos.md DD-05).

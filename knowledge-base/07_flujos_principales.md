# Flujos Principales

## Flujo 1: Reserva online (camino feliz + colisión)

**Disparador**: paciente elige slot libre. **Actor**: paciente (público).

**Pasos**:
1. Frontend `GET /api/profesionales` → lista; `GET /api/disponibilidad?profesional_id=&desde=&hasta=` → slots (cómputo: ventanas − bloqueos − ocupados).
2. Paciente completa nombre+DNI+teléfono+OS+mail (los 5 obligatorios) y confirma.
3. Frontend `POST /api/turnos` con `{profesional_id, inicio, paciente:{...}}`.
4. API en transacción: revalida slot (lock por profesional), crea/actualiza `Paciente` por DNI, crea `Turno reservado` con `fin=inicio+duración` y `token_cancelacion`, encola `Notificacion confirmacion` (siempre — toda reserva tiene mail) + recordatorios 24h/2h, escribe `AuditoriaTurno`.
5. Worker envía confirmación con link `GET /cancelar?token=`; programa recordatorios 24h/2h.
6. Frontend muestra resumen + link de cancelación.

**Casos de error**:
- Slot tomado concurrentemente → 409 + alternativos del mismo día → paciente reelige.
- Faltan obligatorios (incl. mail) → 400 con campos marcados.
- Mail inválido → 400 solo en ese campo.
- Fallo SMTP → la reserva igual se crea; notificación queda `pendiente` con reintentos.

## Flujo 2: Cancelación paciente (≥3h)

**Disparador**: paciente abre link de cancelación del mail. **Actor**: paciente.

**Pasos**:
1. Paciente se identifica solo con `token_cancelacion` (link del mail). Sin sección "mis turnos" por DNI+teléfono (GATE 2026-10-11 PB-01).
2. `DELETE /api/turnos/{id}?token=` ; API verifica `inicio - now() >= 3h`.
3. Si ok: `estado=cancelado`, slot liberado, encola mail de confirmación de cancelación, audita.
4. Si <3h: 422 + mensaje y teléfono del consultorio.

**Casos de error**:
- Token inválido → 403 genérico (sin revelar si el turno existe a terceros).
- Turno ya atendido/cancelado → 422.

## Flujo 3: CRUD recepción (incl. forzar <3h)

**Disparador**: llamada/mostrador o dato inválido. **Actor**: recepción (auth).

**Pasos**:
1. Recepción busca agenda día/semana (`GET /api/profesionales/{id}/agenda`).
2. Crea (`POST /api/turnos` con `origen=recepcion`), edita/reprograma (`PUT`) o cancela (`DELETE`) — toda escritura valida anti-solape (RN-TU-03).
3. Cancelación <3h: UI exige motivo; API la permite solo con rol recepción/admin y escribe `AuditoriaTurno(forzar_cancelacion, motivo)`.
4. Corrección de datos paciente (`PUT /api/turnos/{id}/paciente`) + auditoría.

## Flujo 4: Recordatorios por mail (worker)

**Disparador**: cron/worker cada 5–10 min. **Actor**: sistema.

**Pasos**:
1. Worker toma `Notificacion` en `pendiente` vencidas (confirmaciones inmediatas + recordatorios cuya `enviar_en <= now()` y turno sigue activo).
2. Envía por SMTP; ok → `enviada`; fallo → `intentos++`, backoff; 3 fallos → `fallida` + visible en panel.
3. Si el turno se canceló antes del recordatorio, la notificación se descarta (no se envía).

```
Scheduler → Worker → SMTP → (ok/fallo) → Postgres (estado notif)
                └─→ Panel recepción (fallidas visibles)
```

## Flujo 5: Login staff + día de consultorio

**Disparador**: inicio de jornada. **Actor**: recepción/odontólogo/admin.

**Pasos**:
1. `POST /api/auth/login` (email+password) → cookie httpOnly con sesión/rol.
2. Odontólogo abre "mi agenda del día"; recepción abre agenda multi-profesional + fallidas de mail.
3. Durante el día: recepción crea/bloquea; odontólogo marca `confirmado/atendido/ausente`.
4. Cierre: reporte básico de ocupación del día (US-011).

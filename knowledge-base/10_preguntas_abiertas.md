# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — Mail v1 vs. estándar WA del mercado
**Documento A dice**: Discovery v1 + Ronda 1 P2=(a): recordatorios solo mail; WA post-v1.
**Documento B dice**: market-research C.1/C.3/D.3: 13/18 usan WA; "el mercado exige WA desde el día 1; mail como fallback".
**Impacto**: v1 nace bajo el estándar; ausentismo puede no mejorar lo esperado.
**Resolución propuesta**: mantener P2=(a) por costo (DD-04) pero con gate métrico a v1.1 WA a 60 días (SU-02). No reabrir en v1 salvo que el consultorio lo financie.

### IN-02 — OS obligatoria vs. validación de mercado
**Documento A dice**: Discovery: OS campo obligatorio (sin padrón).
**Documento B dice**: market-research C.2.5: ClinIA valida PUCO/RENAPER; DoctorYa gestiona copagos — "el mercado ya resolvió que se valida".
**Impacto**: v1 acepta OS inexistentes/erróneas; recepción carga con la validación manual.
**Resolución propuesta**: mantener texto libre en v1 (DD-07), llevar validación a v1.1 como primer diferenciador AR.

## Preguntas abiertas (priorizadas) — GATE CERRADO 2026-10-11 (resoluciones FINAL del consultorio)

| Prioridad | Pregunta | Estado gate | Decisor |
|-----------|----------|-------------|---------|
| Alta | PB-01: Cancelación paciente ¿solo por link `token_cancelacion` o también DNI+teléfono en UI? (afecta 03/07 y endpoints) | ✅ RESUELTA — SOLO `token_cancelacion`. Drop DNI+tel UI ("mis turnos"). C-06: only `?token=` credential, 403 genérico otherwise. C-09: only `GET /cancelar?token=`, sin sección DNI+tel. C-05: token por turno only. | Consultorio |
| Alta | PB-02: Mail del paciente ¿obligatorio u opcional? (si obligatorio, RN-TU-01 cambia; si opcional, flujo "sin recordatorio" debe diseñarse) | ✅ RESUELTA — mail OBLIGATORIO. RN-TU-01 cambia: email required + formato válido sino 400 (ese campo). Se elimina el fallback "sin mail no hay recordatorio / sin notificaciones" de C-05/C-08/C-09 — toda reserva tiene mail, confirmación+recordatorios siempre encolados. | Consultorio |
| Alta | PB-03: Worker default ¿APScheduler en-proceso o ARQ+Redis desde el día 1? (costo vs. robustez; SU-03) | ✅ RESUELTA — APScheduler en-proceso (DD-05/SU-03). C-08 queda loop single-process 5-10min, `REDIS_URL` solo documentada, sin servicio Redis día 1. | Tech lead |
| Media | PB-04: Soft vs. hard delete pacientes + derecho al olvido Ley 25.326 (cierra SU-04) | ✅ RESUELTA — HÍBRIDO según propuesta. C-02: soft delete default (`activo=false`, UI dice "desactivar"), DELETE físico permitido SOLO cuando el paciente tiene cero turnos, más procedimiento manual documentado de anonimización para pedidos Ley 25.326 (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos conservados como estadística; sin UI v1, script/endpoint admin documentado). Sin hard-delete con turnos asociados. | Consultorio + tech |
| Media | PB-05: Proveedor SMTP + dominio remitente + backups Postgres (define env vars y costo real) | ✅ RESUELTA — Gmail provisorio + backups en disco del host (local, retención 7 días). C-12: `SMTP_*` para Gmail (app password documentado), script de backup a disco local. Marcar como provisorio/migrable. | Tech lead |
| Media | PB-06: Reporte ocupación ¿solo tabla o también export CSV (anti-cautiverio, C.3.5)? | ✅ RESUELTA — tabla sola, NO CSV en v1. C-11 solo tabla. | Consultorio |
| Baja | PB-07: Frontend ¿Tailwind o CSS modules? (velocidad vs. peso) | ⏸️ DIFERIDA al primer propose frontend (C-09). Se deja abierta, no se fija. | Tech lead |
| Baja | PB-08: Reprogramación por paciente (cambiar fecha sin cancelar) ¿v1 o v1.1? (mercado la tiene; Discovery solo nombra cancelación) | ✅ RESUELTA — v1.1 (reprogramación FUERA de v1). Exclusión de scope confirmada. | Consultorio |

## Resoluciones gate (verbatim FINAL — 2026-10-11, propagar exacto a C-02/C-05/C-06/C-08/C-09/C-11/C-12)

- PB-01: SOLO token_cancelacion. Drop DNI+tel UI ("mis turnos"). C-06: only `?token=` credential, 403 generic otherwise. C-09: only `GET /cancelar?token=`, no DNI+tel section. C-05: token per turno only.
- PB-02: mail OBLIGATORIO. RN-TU-01 changes: email required + valid format else 400 (that field). Remove "sin mail no hay recordatorio / sin notificaciones" fallback from C-05/C-08/C-09 — every reserva has mail, confirmacion+recordatorios always enqueued.
- PB-03: APScheduler en-proceso (DD-05/SU-03). C-08 stays single-process loop 5-10min, REDIS_URL documented only, no Redis service day 1.
- PB-04: HIBRIDO as proposed. C-02: soft delete default (`activo=false`, UI says "desactivar"), physical DELETE allowed ONLY when paciente has zero turnos, plus documented manual anonymization procedure for Ley 25.326 requests (nombre->"Eliminado #id", dni/tel/mail->NULL, turnos kept as stats; no v1 UI, admin script/endpoint documented). No hard-delete with associated turnos.
- PB-05: Gmail provisionally + backups on host disk (local, 7-day retention). C-12: SMTP_* for Gmail (app password documented), backup script local disk. Mark as provisorio/migrable.
- PB-06: tabla sola, NO CSV in v1. C-11 table only.
- PB-07: DEFERRED to first frontend propose (C-09). Leave open, do not fix.
- PB-08: v1.1 (reprogramacion OUT of v1). Confirm scope exclusion.

## Ronda 2 (kb-creator) — resueltas autónomamente donde Discovery/state ya cierra

- RBAC simple vs. ABAC → **simple** (03; escala <50, sin permisos por recurso).
- Notificaciones ¿mail/push/in-app? → **solo mail v1**, asincrónico con reintentos (05 RN-NO, 07 Flujo 4).
- Máquina de estados explícita → **sí, enum con transiciones RN-TU-07**.
- Webhooks externos en v1 → **no** (MP/WA son post-v1; sin webhooks entrantes).
- Auditoría → **append-only en AuditoriaTurno** (04/05).
- Datos versionados/jerárquicos → **no se requieren en v1**.
- No inventado: PB-01…PB-08 quedan abiertas para roadmap-generator/consultorio en vez de adivinarse.

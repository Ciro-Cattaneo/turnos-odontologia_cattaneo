# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Web + API con workers, frontend responsive (no app nativa)
**Decisión**: Ronda 1 P0-sys=(b): web + API backend con workers (mails por cola), frontend web mobile-first.
**Contexto**: mayoría reserva desde el celular; equipo sin capacidad mobile nativa.
**Alternativas consideradas**: app nativa; solo backend sin frontend propio; SaaS de terceros (Dentalink/Odentix).
**Justificación**: responsive cubre el caso de uso a fracción del costo; workers aíslan el envío de mails de la reserva.
**Trade-offs aceptados**: sin push nativo ni offline; se compensa con mail + (post-v1) WA.

### DD-02 — Escala: un consultorio, equipo chico, single tenant
**Decisión**: Ronda 1 P0-scale=(a): <50 personas, un consultorio (Cattaneo), sin `tenant_id` en v1.
**Contexto**: consultorio único, multi-profesional día 1 pero misma recepción.
**Alternativas**: multi-tenant desde el día 1.
**Justificación**: multi-tenant duplica complejidad (aislamiento, facturación por tenant) sin cliente que lo pida.
**Trade-offs**: migrar a multi-tenant después exige backfill; se mitiga reservando la estrategia (DB por tenant vs. columna) en 02.

### DD-03 — Stack: FastAPI + React + Postgres
**Decisión**: Ronda 1 P4=(c): Python FastAPI (monolito modular) + React + Postgres single-instance.
**Contexto**: sin stack obligatorio heredado; costo y velocidad mandan.
**Alternativas**: Node/Next, Django monolito, BaaS (Supabase/Firebase).
**Justificación**: FastAPI da OpenAPI gratis y async barato; Postgres da exclusión anti-solape sin Redis; React cubre responsive con mercado amplio.
**Trade-offs**: equipo debe saber Python+React; BaaS habría sido más rápido pero con costo/lock-in mayor.

### DD-04 — MVP mínimo: flujo base + mail; WA/MP/lista de espera/HC fuera
**Decisión**: Ronda 1 P2=(a): recepción CRUD + agenda día/semana + reserva online + cancela ≥3h + mail. WA, seña MP, lista de espera, HC fuera de v1.
**Contexto**: lanzar barato y medir; el mercado exige WA pero implementarlo bien (API oficial + plantillas) excede el presupuesto v1.
**Alternativas**: v1 con WA primero (recomendación del informe D.3).
**Justificación**: v1 cierra el dolor (dobles reservas, confirmación manual) con mail; WA/MP se dejan como puertas sin código muerto.
**Trade-offs aceptados**: desventaja evidenciada vs. 13/18 que usan WA (riesgo R-03 registrado); se comunica como v1.1 explícito, no como olvido.

### DD-05 — Costo mínimo como prioridad de calidad
**Decisión**: Ronda 1 P5=(d): single host / PaaS barato, Postgres single-instance, worker liviano (APScheduler default).
**Contexto**: consultorio chico, sin DevOps.
**Alternativas**: managed Postgres + queue dedicada + multi-instancia.
**Justificación**: el volumen (<cientos de turnos/día) no justifica réplicas; APScheduler evita operar Redis.
**Trade-offs**: sin HA real; ventana de backup diaria; escalar exige pasar a ARQ/Celery+Redis (camino previsto, no implementado).

### DD-06 — Reserva sin login (solo token)
**Decisión**: paciente sin cuenta en v1; identidad = `token_cancelacion` por turno (única credencial, enviada por mail). Drop DNI+tel UI ("mis turnos"). — GATE 2026-10-11 PB-01.
**Contexto**: fricción mínima = conversión (Fresha/Doctoralia como vara UX).
**Alternativas**: cuenta con email+password o login con DNI; identificación por DNI+teléfono en UI (descartada por el gate).
**Justificación**: el segmento poco digital abandona con registro; el token por mail cubre cancelación.
**Trade-offs**: sin "mis turnos" persistente; riesgo de enumeración mitigado con mensajes genéricos + rate-limit.

### DD-07 — OS como texto obligatorio, sin validar padrón en v1
**Decisión**: campo obligatorio, sin consulta a PUCO/RENAPER en v1.
**Contexto**: validar contra padrón exige integración regulada fuera de presupuesto.
**Alternativas**: validar desde v1 (como ClinIA).
**Justificación**: consciente y documentada; recepción valida manualmente.
**Trade-offs**: deuda explícita; comprometido como diferenciador v1.1 (ver 10).

## Supuestos inferidos

### SU-01 — Recepción mantiene disponibilidades al día
**Supuesto**: recepción actualiza ventanas/bloqueos; si no, hay horarios falsos.
**Origen**: riesgo principal de Discovery §10.
**Riesgo si es falso**: choques y dobles reservas aparentes (no técnicas sino de datos).
**Cómo validar**: UI con "última actualización" (US-002 CA-3) + reporte semanal de slots fantasma.

### SU-02 — Mail alcanza para v1 aunque el mercado pida WA
**Supuesto**: el consultorio acepta lanzar con solo mail y medir ausentismo antes de pagar WA API.
**Origen**: Ronda 1 P2=(a) + restricción de costo.
**Riesgo si es falso**: ausentismo no baja; presión para adelantar WA a mitad de v1.
**Cómo validar**: métrica de ausentismo pre/post mail en 60 días; gate explícito a v1.1 WA.

### SU-03 — Volumen cabe en single host + APScheduler
**Supuesto**: <500 turnos/día, <2k mails/día; sin picos que exijan Redis/Celery.
**Origen**: escala (a) + costo (d).
**Riesgo si es falso**: recordatorios demorados/perdidos en picos.
**Cómo validar**: métricas de latencia de cola desde el día 1; umbral de migración definido (>5k jobs/día o latencia p95 >10 min).

### SU-04 — Híbrido: soft-delete default + físico solo sin turnos + anonimización manual
**Resuelta por GATE 2026-10-11 PB-04**: soft-delete default (`activo=false`, UI dice "desactivar") en pacientes/profesionales; turnos cancelados se conservan; DELETE físico permitido SOLO cuando el paciente tiene cero turnos; pedidos de "derecho al olvido" (Ley 25.326) se resuelven con procedimiento manual documentado de anonimización (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos conservados como estadística; sin UI v1).
**Origen**: inferido (Discovery no lo define; escala chica no exige borrado físico).
**Cómo validar**: C-02 implementa el híbrido + documenta el procedimiento manual (ver 10 PB-04).

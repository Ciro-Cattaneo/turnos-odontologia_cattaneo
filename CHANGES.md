# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto turnos-odontologia_cattaneo.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. **Identificá el change** a implementar (empezá por `C-01`; respetá dependencias y gates).
2. **Leé la KB indicada** en `Leer antes` de ese change (los archivos y secciones listados).
3. **Ejecutá** `/opsx:propose C-NN-<nombre>` para generar `proposal/design/spec/tasks` del change.
4. **Implementá y archivá** con el flujo OpenSpec (`apply` → `archive/sync`).
5. **Marcá el checkbox** (`- [ ]` → `- [x]`) del change completado y avanzá al siguiente desbloqueado.

---

## Árbol de dependencias

```
C-01 foundation-setup
└── C-02 core-models
    ├── C-03 auth-staff-rbac
    │   ├── C-07 crud-recepcion-backend (← necesita C-03 + C-05)
    │   │   ├── C-10 frontend-agenda-staff (← necesita C-04 + C-07)
    │   │   │   └── C-12 deploy-single-host
    │   │   └── C-11 admin-profesionales-reportes (← necesita C-03 + C-07)
    │   │       └── C-12 deploy-single-host
    │   └── C-12 deploy-single-host (vía C-11)
    ├── C-04 agenda-disponibilidad-backend
    │   └── C-05 reserva-online-backend (← necesita C-02 + C-04)
    │       ├── C-06 cancelacion-paciente-backend
    │       │   └── C-09 frontend-reserva-publica (← necesita C-04 + C-05 + C-06)
    │       │       └── C-12 deploy-single-host
    │       ├── C-07 crud-recepcion-backend
    │       └── C-08 notificaciones-mail-worker
    │           └── C-12 deploy-single-host
    └── C-05 (vía C-04)
```

### Paralelismo por fase

```
GATE 0: C-01 foundation-setup ✓
  → C-02 core-models                                    [Agente A]

GATE 1: C-02 core-models ✓     ← PRIMER FORK
  → C-03 auth-staff-rbac                                [Agente A]
  → C-04 agenda-disponibilidad-backend                  [Agente B]

GATE 2: C-03 + C-04 ✓
  → C-05 reserva-online-backend (necesita C-02 + C-04)  [Agente B]

GATE 3: C-05 reserva-online-backend ✓     ← FORK (3 ramas)
  → C-06 cancelacion-paciente-backend                   [Agente B]
  → C-07 crud-recepcion-backend (si C-03 ✓)             [Agente A]
  → C-08 notificaciones-mail-worker                     [Agente C]

GATE 4: C-06 + C-07 + C-08 ✓     ← FORK frontend/admin
  → C-09 frontend-reserva-publica (si C-04 ✓)           [Agente C]
  → C-10 frontend-agenda-staff                          [Agente A]
  → C-11 admin-profesionales-reportes                   [Agente B]

GATE 5: C-09 + C-10 + C-11 ✓
  → C-12 deploy-single-host                             [Agente A]
```

### Camino crítico (7 changes — mínimo irreducible)

```
C-01 → C-02 → C-04 → C-05 → C-08 → C-09 → C-12
```

Rama near-critical de operación (recepción no puede trabajar sin ella):
`C-05 → C-07 → C-10 → C-12`. En la práctica, C-07/C-10 van en paralelo con C-08/C-09 (GATE 4) y no alargan el plan con 3 agentes.

### Plan óptimo con 3 agentes

| Paso | Agente A (Backend Core) | Agente B (Backend Aux) | Agente C (Frontend/Worker) |
|------|-------------------------|------------------------|----------------------------|
| 1 | C-01 foundation-setup | — | — |
| 2 | C-02 core-models | — | — |
| 3 | C-03 auth-staff-rbac | C-04 agenda-disponibilidad | — |
| 4 | — | C-05 reserva-online | — |
| 5 | C-07 crud-recepcion | C-06 cancelacion-paciente | C-08 notificaciones-mail |
| 6 | C-10 frontend-agenda-staff | C-11 admin-reportes | C-09 frontend-reserva-publica |
| 7 | C-12 deploy-single-host | — (revisión/QA) | — (revisión/QA) |

---

## FASE 1 — Fundación y modelos core

### [C-01] `foundation-setup`
- **Estado**: `[x]` completado
- **Scope**:
  - Scaffolding `backend/app/main.py` (FastAPI, routers vacíos, `GET /api/health`), `core/` (config por env, rate-limit base), `db/` (base, session)
  - Scaffolding `frontend/` (React + Vite + React Router, `features/` + `shared/` + `pages/` vacíos)
  - `docker-compose.yml` (web + postgres; worker/redis solo como servicio/stub comentado)
  - `.env.example` versionado con todas las vars de 08 (`DATABASE_URL, SECRET_KEY, ADMIN_EMAIL/PASSWORD, SMTP_*, TZ, CANCEL_HOURS_MIN, SLOT_DEFAULT_MIN, FRONTEND_URL, REDIS_URL opcional`); `.env` en `.gitignore`
  - Alembic inicializado (sin migraciones de dominio todavía), `backend/Dockerfile`
  - Tests base: `pytest + httpx` (health), `ruff` + `Vitest` configurados
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/08_arquitectura_propuesta.md` §Variables de entorno
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico

### [C-02] `core-models`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Paciente, Profesional, Disponibilidad, Bloqueo, Turno, Notificacion, UsuarioStaff, AuditoriaTurno` (atributos/constraints/índices según 04)
  - `Turno`: enum `estado` + `origen`, `token_cancelacion UUID UNIQUE`, columnas reservadas post-v1 `pago_estado NULL, lista_espera_pos NULL` (sin lógica); `canal_recordatorio ENUM(mail)` extensible
  - Constraint anti-solape: `EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin) WITH &&) WHERE (estado IN ('reservado','confirmado'))` + validación app en service
  - Migración Alembic `001_core_models`; seed: roles enum + admin inicial por env (`ADMIN_EMAIL/ADMIN_PASSWORD`, rotar al primer login) + script `seed_demo.py` (staging: 2 profesionales + 20 turnos)
  - `AuditoriaTurno` append-only (sin UPDATE/DELETE por app)
  - Tests: creación de entidades, `UNIQUE(dni)`, exclusión anti-solape concurrente, append-only auditoría
  - ✅ GATE 2026-10-11 PB-04 (HÍBRIDO FINAL): soft delete default (`activo=false`, UI dice "desactivar"); DELETE físico permitido SOLO si el paciente tiene cero turnos; procedimiento manual documentado de anonimización Ley 25.326 (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos conservados como estadística; sin UI v1, script/endpoint admin documentado). Sin hard-delete con turnos asociados.
- **Dependencias**: `C-01`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Entidades
  - `knowledge-base/04_modelo_de_datos.md` §ERD
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-03, §RN-AU-02
  - `knowledge-base/10_preguntas_abiertas.md` §PB-04

---

## FASE 2 — Dominio turnos y agenda (backend)

### [C-03] `auth-staff-rbac`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `POST /api/auth/login` (email+password, hash bcrypt/argon2) → cookie httpOnly con sesión/rol; `POST /api/auth/logout`
  - Dependencia `require_role(...)` por router; odontólogo scoping a su `profesional_id` (solo agenda propia); Admin ⊇ Recepción ⊇ lectura
  - Schemas Pydantic estrictos de login; rate-limit en login; mensajes de error genéricos (no enumerar usuarios)
  - Tests: login/logout, matriz RBAC (03), odontólogo no ve otros profesionales, sin token → 401/403
- **Dependencias**: `C-02`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-01
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/07_flujos_principales.md` §Flujo 5

### [C-04] `agenda-disponibilidad-backend`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `GET /api/profesionales` (público, solo activos) + `GET /api/profesionales/{id}/agenda?vista=dia|semana&fecha=` (staff + cálculo público de slots según flag)
  - `GET /api/disponibilidad?profesional_id=&desde=&hasta=` (público, rate-limited 30 req/min/IP): cómputo `ventanas − bloqueos − turnos activos`; granularidad = `duracion_default_min` del profesional
  - Staff (auth): `CRUD /api/disponibilidades` (día, desde/hasta, vigencia; validación sin solape mismo profesional+día) + `POST /api/bloqueos` (con motivo, `creado_por` staff)
  - Campo `ultima_actualizacion` por profesional para UI (mitiga SU-01)
  - Tests: cómputo de slots (ventanas−bloqueos−ocupados), granularidad 45', sin ventana → sin slots, rate-limit público
- **Dependencias**: `C-02`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Disponibilidad, §Bloqueo
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-01..03, §RN-TU-05
  - `knowledge-base/06_funcionalidades.md` §US-001, §US-002
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 (pasos 1-2)

### [C-05] `reserva-online-backend`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `POST /api/turnos` (público, rate-limited): body `{profesional_id, inicio, duracion_min?, paciente:{nombre, dni, telefono, obra_social, email}}`; validación Pydantic (los 5 obligatorios — mail OBLIGATORIO con formato válido; ✅ GATE 2026-10-11 PB-02: RN-TU-01 cambia, email required + valid format else 400 en ese campo)
  - Transacción: lock por profesional+slot (`SELECT FOR UPDATE` o exclusión PG), upsert `Paciente` por `dni`, crea `Turno reservado` con `fin=inicio+duración`, `token_cancelacion` (✅ GATE PB-01: token por turno only, única credencial paciente), `origen=online`, encola `Notificacion confirmacion` (siempre — toda reserva tiene mail) + recordatorios 24h/2h, escribe `AuditoriaTurno`
  - Slot ocupado concurrente → `409` + alternativos del mismo día; faltantes → `400` por campo; mail inválido → `400` solo ese campo
  - Reserva nunca se bloquea por fallo de mail (encolado fire-and-forget)
  - Tests: camino feliz, colisión concurrente → 409 + alternativos, 400 por campo faltante (incl. mail), upsert por DNI, auditoría escrita, confirmación+recordatorios siempre encolados
  - ✅ GATE 2026-10-11 PB-01+PB-02 FINAL (ver `knowledge-base/10_preguntas_abiertas.md`): sin fallback "sin mail no hay recordatorio".
- **Dependencias**: `C-02, C-04`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01..03, §RN-TU-06
  - `knowledge-base/06_funcionalidades.md` §US-003, §US-004
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/10_preguntas_abiertas.md` §PB-01, §PB-02

### [C-06] `cancelacion-paciente-backend`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `DELETE /api/turnos/{id}` paciente: ÚNICA credencial `token_cancelacion` (query `?token=`). ✅ GATE 2026-10-11 PB-01 FINAL: solo `?token=`, sin DNI+tel, sin "mis turnos".
  - Regla `inicio - now() >= CANCEL_HOURS_MIN (3)`: ok → `estado=cancelado` + slot liberado + encola mail cancelación + audita; `<3h` → `422` + mensaje y contacto del consultorio
  - Credencial inválida → `403` genérico (no revelar existencia); turno ya atendido/cancelado → `422`
  - Tests: cancela ≥3h, rechaza <3h, 403 genérico, idempotencia relativa, auditoría
- **Dependencias**: `C-05`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-04
  - `knowledge-base/06_funcionalidades.md` §US-005
  - `knowledge-base/07_flujos_principales.md` §Flujo 2
  - `knowledge-base/10_preguntas_abiertas.md` §PB-01

### [C-07] `crud-recepcion-backend`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Staff (auth): `POST /api/turnos` con `origen=recepcion` (mismos obligatorios que online), `PUT /api/turnos/{id}` (reprogramar/cambiar duración, valida anti-solape igual que online), `DELETE /api/turnos/{id}` staff (borrado = `cancelado`, no DELETE físico)
  - Forzar cancelación `<3h` solo rol recepción/admin: UI exige motivo → `AuditoriaTurno(forzar_cancelacion, motivo, actor)`
  - `PUT /api/turnos/{id}/paciente` (corrección DNI/tel/OS) + auditoría; `PATCH /api/turnos/{id}/estado` (confirmado/atendido/ausente, solo transiciones RN-TU-07, inválida → 422)
  - `GET /api/turnos/{id}` ficha con datos + historial de cambios (de `AuditoriaTurno`)
  - Tests: CRUD staff, forzar <3h con/sin motivo, transiciones válidas/inválidas, auditoría en cada mutación
- **Dependencias**: `C-03, C-05`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-02, §RN-TU-04, §RN-TU-07, §RN-AU-02
  - `knowledge-base/06_funcionalidades.md` §US-006, §US-007, §US-008
  - `knowledge-base/07_flujos_principales.md` §Flujo 3
  - `knowledge-base/03_actores_y_roles.md` §RBAC

---

## FASE 3 — Notificaciones (worker mail)

### [C-08] `notificaciones-mail-worker`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Encolado: `confirmacion` inmediata al reservar SIEMPRE (toda reserva tiene mail — ✅ GATE 2026-10-11 PB-02); `recordatorio_24h` y `recordatorio_2h` programados (solo si la anticipación lo permite; cada mail incluye link `GET /cancelar?token=`). Sin fallback "sin mail → sin notificaciones".
  - Worker APScheduler en-proceso, loop single-process cada 5–10 min (✅ GATE 2026-10-11 PB-03 FINAL, DD-05/SU-03); `REDIS_URL` solo documentada, sin servicio Redis día 1.
  - Loop cada 5–10 min: toma `Notificacion pendiente` vencida (`enviar_en <= now()`, turno sigue activo); envía por SMTP; ok → `enviada`; fallo → `intentos++` con backoff; 3 fallos → `fallida`
  - Si el turno se canceló antes del recordatorio → descartar (no enviar)
  - `GET /api/notificaciones/fallidas` (staff) para panel recepción; la reserva nunca se bloquea por fallo SMTP
  - Tests: confirmación <5 min, recordatorios condicionales, 3 reintentos → fallida visible, cancelado no recibe recordatorio
- **Dependencias**: `C-05`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01..03
  - `knowledge-base/06_funcionalidades.md` §US-009
  - `knowledge-base/07_flujos_principales.md` §Flujo 4
  - `knowledge-base/10_preguntas_abiertas.md` §PB-03, §PB-05
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (cola liviana + worker)

---

## FASE 4 — Frontend (público + staff)

### [C-09] `frontend-reserva-publica`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `GET /` landing + `GET /reservar` (buscador por profesional/fecha, lista de slots <2s en 4G, no muestra bloqueados/ocupados)
  - Form reserva (nombre+DNI+tel+OS+mail, los 5 obligatorios — ✅ GATE 2026-10-11 PB-02): 400 con campo marcado; éxito → resumen + link cancelación (confirmación+recordatorios siempre encolados, sin aviso "sin mail").
  - `GET /cancelar?token=` ÚNICO (✅ GATE PB-01: sin sección "mis turnos" DNI+tel); error <3h → 422 + contacto consultorio
  - Mobile-first 360px sin zoom horizontal; cliente API en `shared/`; manejo 409 (muestra alternativos mismo día)
  - Tests Vitest: flujo reserva feliz, 400/409/422 renderizados, responsive smoke 360px
  - ✅ GATE 2026-10-11 PB-07 DIFERIDA al primer propose de este change (C-09): stack CSS (Tailwind vs CSS modules) se decide acá, no fijado. PB-08: reprogramación por paciente FUERA de v1 (v1.1), no implementar en este change.
- **Dependencias**: `C-04, C-05, C-06`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-003, §US-004, §US-005
  - `knowledge-base/07_flujos_principales.md` §Flujo 1, §Flujo 2
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura frontend
  - `knowledge-base/10_preguntas_abiertas.md` §PB-01, §PB-02, §PB-07

### [C-10] `frontend-agenda-staff`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Login staff + agenda multi-profesional día/semana (`GET /api/profesionales/{id}/agenda`): slots ocupados/libres/bloqueados con estado y paciente; selector multi-profesional sin recargar datos ajenos; "última actualización" por profesional (US-002 CA-3)
  - UI CRUD recepción (crear con `origen=recepcion`, editar/reprogramar, cancelar + forzar <3h con motivo), corrección datos paciente + historial, marcar confirmado/atendido/ausente (solo transiciones válidas)
  - Panel notificaciones fallidas (de C-08) visible en recepción
  - Tests Vitest: agenda día/semana, CRUD flows, forzar <3h exige motivo, transiciones inválidas bloqueadas en UI
- **Dependencias**: `C-04, C-07`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-001, §US-002, §US-006, §US-008
  - `knowledge-base/07_flujos_principales.md` §Flujo 3, §Flujo 5
  - `knowledge-base/03_actores_y_roles.md` §RBAC
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura frontend

---

## FASE 5 — Admin, reportes y deploy

### [C-11] `admin-profesionales-reportes`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Admin (auth): `CRUD /api/profesionales` (alta con `duracion_default_min` configurable; baja = `activo=false`, conserva historial) + `CRUD /api/usuarios-staff` (rol, link opcional `profesional_id`)
  - `GET /api/reportes/ocupacion?profesional_id=&desde=&hasta=`: tabla por profesional (turnos, atendidos, ausentes, cancelados, % ocupación) + filtro rango fechas; lectura de estados RN-TU-07
  - ✅ GATE 2026-10-11 PB-06 FINAL: tabla sola, NO CSV en v1.
  - Tests: alta/baja profesional, baja conserva turnos históricos, reporte cuadra por período, RBAC (odontólogo solo propios)
- **Dependencias**: `C-03, C-07`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-010, §US-011
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-07
  - `knowledge-base/03_actores_y_roles.md` §RBAC
  - `knowledge-base/10_preguntas_abiertas.md` §PB-06

### [C-12] `deploy-single-host`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `Dockerfile` backend + build frontend servido (estático o mismo compose); `docker-compose.yml` final (web + worker + postgres + redis opcional comentado)
  - `TZ=America/Argentina/Buenos_Aires`, persistencia UTC / display local; CORS `FRONTEND_URL`; `CANCEL_HOURS_MIN=3`, `SLOT_DEFAULT_MIN=30`
  - Docs deploy: instrucciones single host o PaaS barato (Railway/Render/Fly single instance), TLS del PaaS, declaración mínima Ley 25.326 (finalidad, conservación, no cesión)
  - Backups diarios Postgres a disco local del host, retención 7 días (✅ GATE 2026-10-11 PB-05 FINAL: Gmail provisorio + backups host-disk local; script de backup a disco local versionado). SMTP_* = Gmail con app password documentado. Todo marcado PROVISORIO/MIGRABLE.
  - `GET /api/health` liveness para PaaS; `seed_demo.py` solo staging
  - Tests: compose up smoke, health check, variables requeridas faltantes → error claro al boot
- **Dependencias**: `C-08, C-10, C-11`
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad, §Variables de entorno
  - `knowledge-base/02_descripcion_general.md` §Deploy v1
  - `knowledge-base/10_preguntas_abiertas.md` §PB-05
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-05, §SU-03

# Tasks — c-02-core-models

> Ciclo TDD estricto en TODAS las tareas con código: RED (test que falla) → GREEN (mínimo para pasar) → TRIANGULATE (2º ejemplo que rompa la solución ingenua) → REFACTOR (en verde). Referenciar el AC en el docstring del test (ej. `# AC core-models/Solape-borde`). Capas: `unit` (sin DB) / `migration` / `db` (PG real). Nombres `test_<escenario>_<resultado>`, datos ficticios siempre (regla dura 12).

## 0. Precondición de entorno (bloquea solo tareas DB-backed)

- [x] 0.1 Postgres 16 alcanzable antes de tareas DB-backed — verificar: `psql "$DATABASE_URL" -c "select version();"` responde `PostgreSQL 16.x` (fallback: instalador EDB local documentado en README si no hay Docker); dejar constancia de la URL usada (sin secretos) en el resumen del apply. Tareas §1 (pure-unit) pueden avanzar sin PG; §2–§5 DB requieren esta tarea en verde.

## 1. Modelos pure-unit primero (sin DB)

- [x] 1.1 Crear `backend/app/models/` (D-1: un archivo por entidad + `__init__.py` re-exportando para `Base.metadata`) con TDD — test: `backend/tests/test_models_import.py` (capa: unit, sin DB: importa `app.models`, asserts 8 tablas registradas en `Base.metadata`, PK UUID, `timestamptz` en `inicio/fin`) — verificar: `pytest backend/tests/test_models_import.py` verde incl. `# AC core-models/Entidades-persisten` (estructura) y ciclo RED→GREEN visible.
- [x] 1.2 Enums + defaults + nulabilidad D-9a con TDD — test: `backend/tests/test_model_defaults.py` (capa: unit, construye objetos sin DB: `estado` default `reservado`, `canal_recordatorio` default `mail`, `pago_estado/lista_espera_pos` None, `Paciente.dni/tel/mail` nulables a nivel columna con obligatoriedad documentada app) — verificar: `pytest` verde incl. `# AC turno-lifecycle/Canal-default`, `# AC turno-lifecycle/Post-v1-nulas`, `# AC paciente-privacidad/Anonimizacion-NULL-posible`.

## 2. Migración 001 (revisada a mano)

- [x] 2.1 Generar y revisar `backend/alembic/versions/001_core_models.py` (autogenerate + revisión manual: `CREATE EXTENSION citext/btree_gist`, `CREATE TYPE` enums, EXCLUDE textual D-4 exacto, trigger append-only D-8, FK `ON DELETE RESTRICT`, índice parcial `ix_notif_estado`) con TDD — test: `backend/tests/test_migration_001.py` (capa: migration: `alembic upgrade head --sql` contiene `EXCLUDE USING gist`, `tstzrange`, `WHERE (estado`, `citext`, `btree_gist`; `env.py` importa `app.models`) — verificar: `pytest` verde + `alembic -c backend/alembic.ini heads` con una sola head.
- [x] 2.2 Upgrade + downgrade limpios contra PG real — test: mismo `test_migration_001.py` (capa: db: `upgrade head` crea 8 tablas + constraint `no_solape_prof`, `downgrade -1` las elimina, segundo `upgrade head` idempotente) — verificar: `pytest backend/tests/test_migration_001.py` verde incl. `# AC core-models/Migracion-upgrade-downgrade`. Requiere §0.

## 3. Persistencia PG-backed (requiere §0)

- [x] 3.1 Creación de las 8 entidades + `UNIQUE(dni)` + CHECK horarios con TDD — test: `backend/tests/test_core_models_crud.py` (capa: db, fixture `db_session` PG real con rollback por test) — verificar: `pytest` verde incl. `# AC core-models/Crear-ocho-entidades`, `# AC core-models/DNI-duplicado-rechazado`, `# AC core-models/hora_desde-rechazada`. Datos ficticios (`.test`).
- [x] 3.2 Anti-solape EXCLUDE + EDGE half-open `[)` + concurrente con TDD — test: `backend/tests/test_anti_solape.py` (capa: db: solape activo → error exclusión; borde exacto `fin==inicio` → permitido; solape con cancelado → permitido; distinto profesional → permitido; 2 hilos/psycopg concurrentes mismo slot → un ganador) — verificar: `pytest` verde incl. `# AC core-models/Solape-rechazado`, `# AC core-models/EDGE-borde-permitido`, `# AC core-models/Cancelado-no-bloquea`, `# AC core-models/Distinto-profesional`, `# AC core-models/Colision-concurrente`. Marcar borde `<` vs `<=` como objetivo mutación 85%+ en el apply.
- [x] 3.3 Lifecycle `Turno` (token/enum/rango/duración/canal) con TDD — test: `backend/tests/test_turno_lifecycle.py` (capa: db: token duplicado/nulo → rechazo; enum inválido → rechazo; `fin<=inicio` y duración cero y duración inconsistente → rechazo; canal default mail; `whatsapp` v1 → rechazo) — verificar: `pytest` verde incl. todos los `# AC turno-lifecycle/*` (9 escenarios).
- [x] 3.4 PB-04 soft-delete + DELETE solo cero turnos + trigger append-only con TDD — test: `backend/tests/test_paciente_privacidad.py` (capa: db: desactivar conserva turnos + excluye de activos; reactivar; idempotencia; DELETE sin turnos ok; DELETE con turnos (incl. solo-cancelado) → rechazo; `UPDATE`/`DELETE` sobre `AuditoriaTurno` → excepción del trigger; mutación staff escribe auditoría) — verificar: `pytest` verde incl. todos los `# AC paciente-privacidad/*` (12 escenarios).
- [x] 3.5 Doc + script anonimización Ley 25.326 (sin UI) con TDD — test: `backend/tests/test_anonimizacion.py` (capa: db: ejecuta `backend/scripts/anonimizar_paciente.py --paciente-id` ficticio → nombre `"Eliminado #id"`, dni/tel/mail NULL, turnos intactos, B intacto; asserts no existe ruta UI) + artefacto `docs/anonimizacion-ley-25326.md` — verificar: `pytest` verde incl. `# AC paciente-privacidad/Anonimizacion-*` y el doc describe pasos manuales admin-only.

## 4. Seeds (último)

- [x] 4.1 Seed admin idempotente desde env con TDD — test: `backend/tests/test_seed_admin.py` (capa: db: corre seed 2× con `ADMIN_EMAIL` ficticio → exactamente 1 `UsuarioStaff` admin; password hasheada no plaintext) — verificar: `pytest` verde incl. `# AC core-models/Seed-admin-idempotente`. Nota: rotación al primer login = C-03, aquí solo creación.
- [x] 4.2 `backend/scripts/seed_demo.py` staging-only (2 profesionales + 20 turnos ficticios) con TDD — test: `backend/tests/test_seed_demo.py` (capa: db/staging: en staging crea 2+20 sin datos reales; con `ENV=prod` rehúsa) — verificar: `pytest` verde incl. `# AC core-models/seed_demo-ficticio` y `ruff check` limpio.

## 5. Verificación integrada del change

- [x] 5.1 Corrida verde completa + validación OpenSpec — verificar: `pytest backend/tests/` (requiere §0), `ruff check backend/ && ruff format --check backend/`, `alembic -c backend/alembic.ini heads` una head, `EXPLAIN` smoke sobre `ix_turno_prof_inicio` adjuntado como evidencia (volumen realista queda follow-up C-04/C-11), y `openspec validate --change c-02-core-models` sin errores; dejar constancia del reporte (qué test cubre cada AC) en el resumen del apply.

## Archive note (2026-10-12, `/opsx:archive c-02-core-models`)

- **Revisión D-4 (authoritative)**: el design original planteaba la duración solo a nivel app; el apply agregó el DB CHECK `ck_turno_duracion_min` (`duracion_min = fin − inicio` en minutos) como invariante autoritativa. El futuro C-05 suma validación Pydantic 400 (UX/fast-fail), pero la DB es la última palabra.
- **Handoff a C-03**: hash admin PBKDF2-HMAC-SHA256 stdlib es TRANSITORIO (sin dependencia externa en v1); C-03 (`auth-staff-rbac`) lo reemplaza por el esquema definitivo + rotación al primer login.
- **Nota PG**: apply verificado contra PG 18.6 local (125 pytest verde, ruff limpio, `alembic heads` única `001_core_models`, `alembic check` sin drift); deploy v1 apunta a PG 16 — re-validar `001_core_models` (extensiones `citext`/`btree_gist`, EXCLUDE) en imagen PG16 antes de producción.
- **Handoffs abiertos**: `relationship()`s SQLAlchemy diferidos (sin navegación ORM aún); shapes JSONB de payloads/notificaciones los definen C-07/C-08; `Paciente.email` VARCHAR-vs-CITEXT sigue abierto (decidir en C-03 o C-05).
- **Specs sincronizadas**: `core-models`, `turno-lifecycle`, `paciente-privacidad` (nuevas, solo ADDED) → `openspec/specs/`.

## Workflow follow-up

- Archivar el change (`/opsx:archive`) tras la revisión humana y marcar `[ ] C-02` → `[x]` en CHANGES.md.
- C-03 (`auth-staff-rbac`) y C-04 (`agenda-disponibilidad-backend`) quedan desbloqueados (GATE 1 fork): consumen `app.models` + `001_core_models`.
- Re-ejecutar en máquina con Docker/PG si §0 se resolvió con EDB local: `docker compose up` smoke + migración desde cero.

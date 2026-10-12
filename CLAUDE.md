# turnos-odontologia_cattaneo — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Stack Tecnológico

| Capa | Tecnologías | Versión mínima |
|------|--------------|----------------|
| Backend API | Python + FastAPI (monolito modular, routers por dominio) | Python 3.12, FastAPI ≥0.115 |
| ORM / migraciones | SQLAlchemy 2.x + Alembic | 2.0 / 1.13 |
| Base de datos | Postgres single-instance (sin réplica en v1) | Postgres 16 |
| Workers / colas | APScheduler en-proceso, loop single-process 5–10 min (PB-03; `REDIS_URL` solo documentada); escalar a ARQ/Celery + Redis solo si el volumen lo exige | APScheduler en-proceso |
| Envío de mail | SMTP Gmail provisorio + app password (migrable — PB-05) vía cola con reintentos | — |
| Frontend | React + Vite + React Router, responsive mobile-first, sin framework UI pesado (CSS modules o Tailwind a confirmar) | React 18+, Vite 5+ |
| Auth staff | Sesión por token (JWT httpOnly o session cookie) para recepción/odontólogo/admin; paciente sin login en v1 | — |
| Deploy v1 | Single host (Docker Compose: web + worker + Postgres) o PaaS barato (ej. Railway/Render/Fly single instance) | Docker 24+ |
| Tests / lint | pytest + httpx (backend), Vitest (frontend), ruff | — |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Entender propósito y alcance v1 |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura, API REST |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, permisos |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, migraciones |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas (RN-TU/RN-AG/RN-NO/RN-PA/RN-AU) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica (US-001…US-011) |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E (reserva, cancelación, recepción, worker, login) |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Patrones, estructura, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones DD-01…DD-07 + supuestos SU-01…SU-04 |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Inconsistencias y gate PB-01…PB-08 (cerrado 2026-10-11) |
| [README.md](knowledge-base/README.md) | Índice + resumen ejecutivo |

> ⚠️ Gate PB-01…PB-08 ya cerrado (2026-10-11, ver `10_preguntas_abiertas.md` + `CHANGES.md`). IN-01 (mail vs WA) e IN-02 (OS texto libre) quedan como riesgo aceptado v1 con puerta a v1.1 — no reabrir en v1 salvo orden explícita.

---

## Skills Disponibles

Fuente de verdad: `.atl/skill-registry.md` (generado por `skill-registry`). Filas adaptadas a las skills realmente instaladas.

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| Backend Core | FastAPI/SQLAlchemy/Alembic/Postgres, turnos + agenda + anti-solape | `supabase-postgres-best-practices`, `sql-optimization`, `backend-development`, `prisma-postgres-setup` (solo disciplina conexión/env — el proyecto usa SQLAlchemy, no Prisma ORM) |
| Backend Aux | Auth staff/RBAC, servicios, seguridad, notificaciones mail | `backend-development`, `supabase-postgres-best-practices` |
| Frontend | React + Vite + React Router, mobile-first | `vercel-react-best-practices` |
| Transversal (todos) | TDD + calidad de tests | `tdd-guide`, `test-guard` |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; versionado en el repo). Esta tabla solo mapea skill→rol.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 12 changes en 5 fases.
- **Camino crítico** (7): `C-01 → C-02 → C-04 → C-05 → C-08 → C-09 → C-12`.
- **Primer change**: `C-01 foundation-setup` (scaffolding backend/frontend, compose, `.env.example`, Alembic, tests base; sin dependencias; governance BAJO).
- **Rama near-critical recepción**: `C-05 → C-07 → C-10 → C-12` (va en paralelo con C-08/C-09 en GATE 4, no alarga el plan con 3 agentes).
- **Gates**: GATE 0: C-01 → GATE 1 (fork): C-03 + C-04 → GATE 2: C-05 → GATE 3 (fork 3 ramas): C-06 + C-07 + C-08 → GATE 4 (fork frontend/admin): C-09 + C-10 + C-11 → GATE 5: C-12.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras

> No existe `~/.claude/CLAUDE.md` global — este proyecto no hereda nada y carga sus universales aquí mismo (las reglas 9 y 11 cubren TDD/testing y no-commitear/commits convencionales). Todo lo de abajo es contrato específico del proyecto.

Son contrato; romperlas es un defecto. Formato `NUNCA X → hacer Y`:

1. NUNCA schema Pydantic permisivo -> extra='forbid' + 400 con detalle por campo.
2. NUNCA SQL concatenado ni solape solo en app -> parametrizadas + EXCLUDE USING gist + SELECT FOR UPDATE en reserva.
3. NUNCA hard-delete con turnos -> soft activo=false ("desactivar"); DELETE fisico solo cero turnos; Ley 25.326 solo anonimización manual documentada.
4. NUNCA otra credencial paciente que el token -> solo ?token=; 403 generico; sin "mis turnos" DNI+tel.
5. NUNCA reserva sin 5 campos ni notificaciones condicionales -> mail obligatorio; confirmacion+recordatorios siempre encolados; fallo SMTP nunca bloquea.
6. NUNCA worker fuera de proceso en v1 -> APScheduler en-proceso 5-10min; REDIS_URL solo documentada; 3 reintentos backoff, fallida visible.
7. NUNCA SELECT * ni OFFSET en agenda/reportes -> columnas explicitas, keyset, indices compuestos + partial en estado.
8. NUNCA any ni componentes anidados -> tipado estricto, sin barrels, mobile-first 360px.
9. NUNCA test con mocks internos -> TDD red-green-refactor, mocks solo bordes, DB real si persistencia es sujeto, test_<escenario>_<resultado> + parametrizacion.
10. NUNCA secreto en repo -> todo por env (Gmail provisorio + backups host-disk 7d migrables); TZ America/Argentina/Buenos_Aires, persistir UTC.
11. NUNCA commit/build sin pedido -> no commitear/pushear salvo orden explicita; conventional commits sin co-autoria IA.
12. NUNCA datos reales de pacientes en repo/ejemplos/tests/capturas -> usar solo datos ficticios (Ley 25.326, ver knowledge-base).

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → respetando las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.

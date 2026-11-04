# Evidencia — re-revisión `turno-spec-review` de C-05 (post-corrección)

- **Fecha**: 2026-11-02
- **Skill aplicada**: `turno-spec-review`, siguiendo el procedimiento de `.opencode/skills/turno-spec-review/SKILL.md`. La sesión arrancó antes de crear la skill, así que la invocación por la herramienta se verificó aparte en un proceso nuevo (`05-invocacion-sesion-nueva.md`).
- **Change**: `openspec/changes/c-05-reserva-online-backend/`
- **Modo**: revisión de solo lectura sobre los artefactos corregidos. No se implementó código, no se archivó el change y no se hicieron commits. No se tocaron `CHANGES.md`, `AGENTS.md`, `CLAUDE.md`, `README.md` ni `.atl/skill-registry.md`.

## Artefactos y fuentes revisadas

| Tipo | Ruta |
|---|---|
| Change | `openspec/changes/c-05-reserva-online-backend/proposal.md` |
| Change | `openspec/changes/c-05-reserva-online-backend/design.md` |
| Change | `openspec/changes/c-05-reserva-online-backend/tasks.md` |
| Spec delta | `openspec/changes/c-05-reserva-online-backend/specs/reserva-online/spec.md` |
| Informe previo | `docs/skills-mcp/evidencias/02-skill-review-c05-antes.md` |
| KB | `knowledge-base/04_modelo_de_datos.md` §Paciente, §Turno, §Notificacion, §AuditoriaTurno |
| KB | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01..07, §RN-AG-01..03, §RN-NO-01..03, §RN-PA-01..02, §RN-AU-01..03 |
| KB | `knowledge-base/06_funcionalidades.md` §US-003, §US-004, §US-009 |
| KB | `knowledge-base/07_flujos_principales.md` §Flujo 1, §Flujo 4 |
| KB | `knowledge-base/10_preguntas_abiertas.md` §PB-01, §PB-02, §PB-03, §PB-04 |
| Roadmap | `CHANGES.md` §C-05 |
| Reglas duras | `AGENTS.md` reglas 1-12 |
| Spec base | `openspec/specs/turno-lifecycle/spec.md` |
| Código | `backend/app/main.py` |
| Código | `backend/app/core/ratelimit.py` |
| Código | `backend/app/modules/agenda/slot_service.py` |
| Código | `backend/app/modules/agenda/public.py` |
| Código | `backend/app/models/{turno,paciente,notificacion,auditoria,profesional}.py` |
| Código | `backend/alembic/versions/001_core_models.py` |

**Inventario**: 9 `### Requirement:` y 42 `#### Scenario:` en `specs/reserva-online/spec.md`. No hay artefactos faltantes del change.

## Reglas aplicables extraídas (sin parafrasear umbrales)

- `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01: cinco obligatorios, mail obligatorio con formato válido, 400 en ese campo; confirmación + recordatorios siempre encolados.
- §RN-TU-02: duración default 30, personalizable por turno y por profesional.
- §RN-TU-03: sin dos turnos activos superpuestos; garantía por `SELECT FOR UPDATE` del slot o EXCLUDE Postgres; slot ocupado → 409 + alternativos del mismo día.
- §RN-TU-05: slots = ventanas − bloqueos − turnos activos.
- §RN-TU-06: `token_cancelacion` es la única credencial; sin DNI+teléfono ni "mis turnos".
- §RN-TU-07: solo `reservado`/`confirmado` ocupan slot; `cancelado` no bloquea.
- §RN-AG-01: sin ventana no hay slots.
- §RN-AG-02: granularidad = `duracion_default_min`.
- §RN-NO-01: confirmación inmediata siempre; recordatorios 24h/2h si la anticipación lo permite.
- §RN-NO-02: envío asincrónico, 3 reintentos con backoff, fallo no bloquea la reserva.
- §RN-PA-01: obra social texto libre obligatorio en v1.
- §RN-PA-02: DNI único; teléfono mutable.
- §RN-AU-02: toda mutación staff sobre turnos escribe auditoría append-only.
- §RN-AU-03: rate-limit en endpoints públicos.
- `AGENTS.md` regla dura 1: `extra='forbid'` + 400 con detalle por campo.
- `AGENTS.md` regla dura 2: SQL parametrizado + `EXCLUDE USING gist` + `SELECT FOR UPDATE` en reserva.
- `AGENTS.md` regla dura 3: soft-delete por defecto (`activo=false`); DELETE físico solo con cero turnos.
- `AGENTS.md` regla dura 4: solo `?token=`, 403 genérico, sin DNI+teléfono ni "mis turnos".
- `AGENTS.md` regla dura 5: mail obligatorio; confirmación + recordatorios siempre encolados; fallo SMTP nunca bloquea.
- `AGENTS.md` regla dura 7: columnas explícitas, sin `SELECT *` ni OFFSET en agenda/reportes.
- `knowledge-base/10_preguntas_abiertas.md` §PB-01: solo token por turno.
- §PB-02: mail obligatorio; se elimina el fallback "sin mail no hay recordatorio".
- §PB-04: soft-delete default; DELETE físico solo con cero turnos; anonimización manual documentada.

## Tabla de hallazgos

| ID | tipo | ubicación (archivo:sección) | regla citada | hallazgo | corrección sugerida | severidad |
|---|---|---|---|---|---|---|
| — | — | — | — | Sin hallazgos pendientes. H-01..H-14 quedaron cerrados; el detalle está en §Cierre de hallazgos. | — | — |

**Conteo por severidad**: bloqueante 0; mayor 0; menor 0. Total 0.

## Verificación contra el código

| # | Comprobación | Resultado | Evidencia |
|---|---|---|---|
| 1 | El lock por profesional es viable: `Profesional.id` es PK y la reserva puede hacer `SELECT ... FOR UPDATE` sobre esa fila | **OK** | `backend/app/models/profesional.py:25` define `id` como PK; `backend/app/db/session.py` entrega la `Session` de la transacción. El lock no requiere migración ni constraint nuevo. |
| 2 | `parse_body_or_400` no existe todavía y el handler global deja el prefijo `body` | **OK (documentado)** | `backend/app/main.py:56` sigue armando `campo` con `".".join(loc)`; la tarea 1.3 crea el helper local que quita `body`, tal como exige R2. El contrato de la spec ya no depende solo del handler global. |
| 3 | La firma de rate-limit permite fijar límite, ventana y reloj | **OK** | `backend/app/core/ratelimit.py:62-68`: `check_public_rate_limit(key, *, now=None, limit=30, window_s=60) -> tuple[bool, float]`. La clave `turnos-publico:{ip}` es distinta de `agenda-publica:{ip}` de C-04 (`backend/app/modules/agenda/public.py:41`). R7 fija 10/60 s y `Retry-After` hasta el reset. |
| 4 | El cómputo de slots permite reutilizar `slot_service` y agrupar bloques contiguos | **OK** | `backend/app/modules/agenda/slot_service.py:71-114` devuelve slots puntuales `[inicio, fin)` y los fetchers `fetch_ventanas`/`fetch_bloqueos`/`fetch_turnos_activos` están parametrizados. R4 S2/S3/S5 y D-6 se pueden verificar sin duplicar la semántica. |
| 5 | Constraints, enums y token usados por las correcciones ya existen | **OK** | `backend/app/models/turno.py:60-65` define `ck_turno_duracion_min` y `ux_turno_token`; `backend/alembic/versions/001_core_models.py:40-42` define `no_solape_prof` con `estado IN ('reservado','confirmado')`; `backend/app/models/notificacion.py:15-29` define `NotifTipo`/`NotifEstado`; `backend/app/models/auditoria.py:22` deja `actor_id` nullable. |
| 6 | El riesgo de serialización de datetimes en JSONB está cubierto por contrato | **OK** | `backend/app/models/notificacion.py:67` declara `payload` JSONB NOT NULL y `backend/app/models/auditoria.py:29` declara `detalle` JSONB NOT NULL. D-7, D-8 y los escenarios R1 S5, R1 S7 y R6 S2 exigen strings ISO-8601 UTC, por lo que `json.dumps` no recibe `datetime` crudos. |
| 7 | El escenario de concurrencia con lock es verificable con dos transacciones reales | **OK** | D-2 y D-12 fijan el lock al inicio de la transacción; R5 S2 verifica que la segunda espera el lock y termina en `409`, y R5 S3 verifica que el EXCLUDE sigue siendo la autoridad final si una escritura no toma el lock. `psycopg` 3.3.4 expone `exc.orig.diag.constraint_name`, ya verificado en el informe previo. |

## Trazabilidad escenario → tarea

Los 42 escenarios tienen tarea y test propuesto en `tasks.md`. Resumen por requisito:

| Requisito | Escenarios | Tareas que los verifican |
|---|---:|---|
| R1 Reserva online crea turno, paciente, notificaciones y auditoría | 8 | 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7 |
| R2 Validación estricta de los cinco datos y del mail | 7 | 1.2, 1.4 |
| R3 Duración consistente con la granularidad | 3 | 1.4, 3.1 |
| R4 Revalidación del slot contra la disponibilidad calculada | 6 | 3.2, 3.3, 3.4, 3.5, 3.6, 3.7 |
| R5 Anti-solape y colisión concurrente con un solo ganador | 4 | 3.8, 3.9, 3.10, 3.11 |
| R6 Encolado de notificaciones no bloqueante | 5 | 4.1, 4.2, 4.3, 4.4, 4.5 |
| R7 Rate limit del endpoint público de reserva | 3 | 5.1, 5.2, 5.3 |
| R8 Profesional inexistente o inactivo | 3 | 3.12 |
| R9 Token de cancelación como única credencial | 3 | 2.6 |

### Tareas que no mapean a un escenario

Están justificadas en `tasks.md` y son de proceso o de soporte, no verificaciones de escenario:

- 1.1: verificación de que no hace falta migración (precondición de D-13).
- 1.3: implementación de schemas y `parse_body_or_400` (soporte de R2).
- 4.6: documentación del contrato de `payload` y de la interpretación H-14 (soporta R6 S2 y R1 S7).
- 6.1-6.5: integración, regresión, alcance, validación OpenSpec y cierre del apply log.

No hay tareas huérfanas sin justificación ni escenarios sin tarea.

## Escenarios por tipo

- **Feliz**: 10
- **Error de negocio**: 16
- **Borde**: 16
- **Total**: 42

Distribución por requisito (feliz / error / borde):

| Requisito | Feliz | Error | Borde | Total | Justificación de tipo faltante |
|---|---:|---:|---:|---:|---|
| R1 | 3 | 0 | 5 | 8 | Los errores 400/409 se especifican en R2-R5 para no duplicar escenarios. |
| R2 | 0 | 6 | 1 | 7 | El caso feliz se cubre en R1 S1. |
| R3 | 1 | 1 | 1 | 3 | — |
| R4 | 1 | 3 | 2 | 6 | — |
| R5 | 1 | 2 | 1 | 4 | — |
| R6 | 1 | 1 | 3 | 5 | — |
| R7 | 1 | 1 | 1 | 3 | — |
| R8 | 1 | 1 | 1 | 3 | — |
| R9 | 1 | 1 | 1 | 3 | — |

Ningún requisito queda con menos de tres escenarios. R1 y R2 tienen justificación explícita en la spec para el tipo que no aplica dentro de su bloque.

## Validación OpenSpec

- `openspec validate c-05-reserva-online-backend --strict` → `Change 'c-05-reserva-online-backend' is valid` (`EXIT=0`).
- `openspec status --change c-05-reserva-online-backend --json` → `isPlanningComplete=true`, `isComplete=true`; proposal, specs, design y tasks en `done`.

## Cierre de hallazgos

| Hallazgo | Estado | Dónde se corrigió / motivo |
|---|---|---|
| H-01 (bloqueante, regla dura 2) | Corregido | `design.md` §D-2 y §D-12 incorporan `SELECT ... FOR UPDATE` sobre la fila del profesional al inicio de la transacción, con el orden lock → validaciones → pre-validación → upsert → turno → encolado → auditoría → commit; el EXCLUDE queda como autoridad final. `spec.md` §R5 agrega R5 S2 (segunda transacción espera el lock y termina en 409) y R5 S3 (EXCLUDE como autoridad final). `tasks.md` §3.9 y §3.10 agregan las verificaciones. |
| H-02 (mayor, RN-TU-01 / duro 1) | Corregido | `spec.md` §R2: valores vacíos o solo espacios se tratan como faltantes; escenario R2 S2 y tareas 1.2/1.3. |
| H-03 (mayor, duro 1) | Corregido | `spec.md` §R2 agrega campo extra en la raíz (`notas`) como R2 S5 y R9 S3; tarea 1.2 incluye `test_reserva_campo_extra_raiz_400`. |
| H-04 (mayor, RN-TU-02 / RN-AG-02) | Corregido | `spec.md` §R3 agrega `duracion_min=0` y `-30` como R3 S2; tarea 1.4 incluye `test_reserva_duracion_cero_o_negativa_400` parametrizado. |
| H-05 (mayor, RN-AG-02 / RN-TU-05) | Corregido | `spec.md` §R4 declara el rechazo de `inicio` no alineado y el bloque contiguo con segundo slot ocupado como R4 S2 y R4 S3; tareas 3.3 y 3.4. |
| H-06 (mayor, RN-TU-03) | Corregido | `spec.md` §R4 fija que los alternativos son bloques de la `duracion_min` pedida (o default), alineados; R4 S5 lo verifica y tarea 3.6 lo testea. |
| H-07 (mayor, RN-NO-01) | Corregido | `spec.md` §R6 fija comparaciones estrictas (`inicio - 24h > now`, `inicio - 2h > now`) y agrega R6 S3 (<2h), R6 S4 (=24h) y R6 S5 (=2h); tareas 4.3-4.5. |
| H-08 (mayor, RN-AU-03) | Corregido | `spec.md` §R7 fija 10 req/60 s/IP (D-9), `Retry-After` hasta el reset y el borde 10/11 como R7 S2; tarea 5.2. |
| H-09 (mayor, RN-PA-02 / RN-TU-03) | Corregido | `spec.md` §R4 S1-S3 y §R5 S1-S3 exigen que un 409 no cree ni actualice `paciente`; tareas 3.2-3.4, 3.8-3.10. |
| H-10 (mayor, PB-04 / duro 3) | Corregido | `design.md` §D-3 traza la decisión a R1 S4; `spec.md` §R1 S4 exige reserva con `Paciente.activo=false`, sin reactivarlo y sin duplicar; tarea 2.4. En Open Questions quedó marcada como decisión cerrada. |
| H-11 (mayor, RN-NO-01 / RN-AU-02) | Corregido | `design.md` §D-7 y §D-8 fijan datetimes como strings ISO-8601 UTC; `spec.md` R1 S5, R1 S7 y R6 S2 lo verifican; tareas 2.5, 2.7, 4.2 y 4.6. |
| H-12 (menor, RN-TU-06) | Corregido | `spec.md` §R1 S6 fija `FRONTEND_URL.rstrip("/") + "/cancelar?token=..."` con `FRONTEND_URL` terminada en barra; `design.md` §D-11 ya lo documenta; tarea 2.6. |
| H-13 (menor, RN-NO-01) | Corregido | `spec.md` §R1 S1, §R1 S6 y §R6 S1 incluyen `notificaciones_encoladas` en la respuesta, alineado con `design.md` §D-11; tareas 2.1, 2.6 y 4.1. |
| H-14 (menor, duro 5 vs. RN-NO-01) | Corregido | `design.md` §D-7 explicita que "siempre encolados" significa sin fallback por falta de mail y que los recordatorios dependen de la anticipación (RN-NO-01); `spec.md` §R6 lo declara en el requisito y `tasks.md` §4.6 lo documenta. No se cambió la regla dura ni la KB. |

Ningún hallazgo fue rechazado.

## Veredicto

**LISTO**

Motivo: no quedan hallazgos bloqueantes, mayores ni menores; los 9 requisitos tienen al menos tres escenarios o justificación explícita del tipo que no aplica; los 42 escenarios tienen resultado observable y tarea de verificación con test propuesto y capa; y `openspec validate --strict` pasa con planificación completa.

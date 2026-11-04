# Aplicación de la skill propia y del MCP al proyecto

Fecha: 2026-11-02. Repo: `turnos-odontologia_cattaneo`. Entregable de la Parte 2 del TP.

## 1. Qué se hizo y por qué

El proyecto ya tenía fundación (KB de 10 archivos, `CHANGES.md` con 12 changes, OpenSpec inicializado) y C-04 archivado. Para el TP se eligió el siguiente change del camino crítico, **C-05 `reserva-online-backend`** (`POST /api/turnos`), y se lo llevó hasta planificación completa **sin implementar**. Se incorporaron dos capacidades nuevas:

- **Skill propia `turno-spec-review`**: no existía nada que auditara specs de turnos contra las RN-* y las 12 reglas duras antes de codear; `tdd-guide`/`test-guard` revisan código, no artefactos.
- **MCP `context7`**: el proyecto ya usaba `engram` como memoria; faltaba documentación vigente de SQLAlchemy/Pydantic/FastAPI. Es de solo lectura y no requiere API key.

Ambas quedaron versionadas/documentadas: la skill en `.opencode/skills/turno-spec-review/SKILL.md`, el MCP en `README.md` §MCP y en la config global de opencode (sin secretos). Se registraron además en la fundación (`.atl/skill-registry.md`, `AGENTS.md`/`CLAUDE.md`, `skills-instaladas.txt`) para que cualquier agente las descubra.

## 2. Resultados obtenidos

**Change planificado**: 9 requirements, **42 escenarios** (10 feliz, 16 error de negocio, 16 borde) y **37 tareas** con test propuesto y capa (API con `httpx` + DB real `turnos_test`). `openspec validate c-05-reserva-online-backend --strict` → `valid`; `status` → planificación completa. El change **no** se implementó, archivó ni marcó como hecho en `CHANGES.md`.

**Revisión de la skill**: dos pasadas reales, antes y después de corregir.

| Pasada | Hallazgos | Veredicto |
|---|---|---|
| Antes (`02-…-antes.md`) | 14: **1 bloqueante**, 10 mayores, 3 menores | `NO LISTO` |
| Después (`03-…-despues.md`) | 0 (los 14 cerrados) | `LISTO` |
| Verificación en sesión nueva (`05-…`) | 0 sobre el requirement de anti-solape | `LISTO` |

**Uso del MCP**: dos consultas que cambiaron decisiones del design (`01-context7-consultas.md`):
1. SQLAlchemy `begin_nested()`/SAVEPOINT: sin savepoint, tras un `IntegrityError` la transacción queda abortada y no se pueden calcular alternativos; con savepoint sí. Confirmó D-2.
2. Pydantic v2 `extra_forbidden` y `loc` anidado: permite un único error en `paciente.email`. Además confirmó que `EmailStr` rechaza el TLD `.test` que exige la regla dura 12, así que se usa un patrón propio (igual que `LoginIn` de C-03).

## 3. Revisión crítica: el defecto que encontró la skill

El hallazgo bloqueante fue real y no cosmético. El primer `design.md` (§D-2) decidía **no** usar `SELECT FOR UPDATE` y confiar solo en el `EXCLUDE` de Postgres, argumentando que “no hay fila de slot que bloquear”. La skill lo cruzó con `AGENTS.md` regla dura 2 (“`EXCLUDE USING gist` **+** `SELECT FOR UPDATE` en reserva”) y lo marcó bloqueante: la regla dura prevalece sobre la KB y sobre el diseño.

- **Antes**: solo EXCLUDE; la segunda transacción llegaba al `INSERT` y dependía del error de DB.
- **Después**: `SELECT … FOR UPDATE` sobre la fila de `profesional` al inicio de la transacción (serializa reservas del mismo profesional, no entre profesionales), con el EXCLUDE como autoridad final. Se agregaron dos escenarios: la segunda transacción espera el lock y termina en 409; y el EXCLUDE sigue atajando escrituras que no toman el lock.

Otros hallazgos que valían la pena: alternativos que no respetaban `duracion_min` (H-06), 409 que dejaba un `paciente` del upsert (H-09), bordes `=24h`/`=2h` sin definir (H-07), datetimes crudos en columnas JSONB que `json.dumps` no serializa (H-11), rate limit circular sin número verificable (H-08) y la tensión entre la regla dura 5 (“siempre encolados”) y RN-NO-01 (H-14).

La skill también **verificó contra el código** en vez de suponer: el anti-solape ya existía desde `001_core_models` (`btree_gist` + `no_solape_prof` half-open `[)`, parcial por estado) con tests de concurrencia, así que C-05 no necesita migración; `check_public_rate_limit` acepta límite, ventana y reloj, y su clave no colisiona con C-04; `psycopg` 3.3.4 expone `diag.constraint_name`.

## 4. Archivos modificados y motivo

| Archivo | Cambio | Motivo |
|---|---|---|
| `docs/skills-mcp/investigacion.md` | Nuevo | Ficha de la Parte 1: necesidad, opciones, elección y pasos. |
| `.opencode/skills/turno-spec-review/SKILL.md` | Nuevo | Skill propia (entradas, procedimiento, checklist de bordes, formato y veredicto). |
| `openspec/changes/c-05-reserva-online-backend/{proposal,design,tasks}.md` + `specs/reserva-online/spec.md` | Nuevos | Planificación del change; corregidos tras la revisión. |
| `.atl/skill-registry.md` | Fila + compact rules | Que el orquestador resuelva la skill al delegar. |
| `AGENTS.md` y `CLAUDE.md` | Fila de skill, sección de la skill propia y §MCP | Instrucciones del proyecto; ambos archivos se mantienen idénticos. |
| `README.md` | §MCP + estructura | Instalación reproducible de Context7 sin secretos. |
| `skills-instaladas.txt` | Sección “Skills propias” | Inventario del entorno. |
| `CHANGES.md` | Línea “Change preparado” en §C-05 | Trazabilidad roadmap → change, sin marcarlo implementado. |
| `docs/skills-mcp/evidencias/01..05` | Nuevos | Evidencia de las consultas MCP, de las dos pasadas de la skill, del descubrimiento y de la invocación en un proceso nuevo. |

No se modificó código de `backend/` ni de `frontend/`, no se agregaron dependencias y no se hizo commit (regla dura 11).

## 5. Limitaciones

- **La skill audita artefactos, no implementación.** No reemplaza a `test-guard`/`tdd-guide` ni detecta bugs de código; su valor termina donde empieza el apply.
- **Método de invocación**: las dos pasadas se ejecutaron aplicando el `SKILL.md` en la sesión original, que arrancó antes de que la skill existiera; la invocación por la herramienta se comprobó en un proceso nuevo con una revisión acotada (`05`).
- **Cobertura de Context7**: cubre SQLAlchemy, Pydantic y FastAPI, pero no las garantías de constraints de Postgres (`EXCLUDE`, `btree_gist`); eso se verificó leyendo la migración y los modelos, no el MCP.
- **Desviación de contrato declarada**: C-05 devuelve `campo="paciente.email"` con un helper local que quita el prefijo `body`, mientras el handler global de `main.py` devuelve `body.paciente.email`. Se documentó en D-4 y en la evidencia 03; unificar el handler global quedó como candidato para C-09/C-10, porque tocarlo cambia C-03/C-04.
- **El lock no se probó en ejecución**: la concurrencia quedó especificada y con tareas de test, pero el change no se implementó, así que no hay evidencia empírica del 409 bajo dos transacciones reales.
- **Sin commits**: el TP pide historial del proceso; por la regla dura 11 los commits quedan pendientes de autorización explícita.
- La revisión no reemplaza la decisión del dueño: los umbrales (10 reservas/60 s, 5 alternativos, 3 h de cancelación) se citaron de la KB/`CHANGES.md`, no se inventaron.

## 6. Cómo reproducirlo

```powershell
opencode mcp list                 # context7 y engram connected
opencode debug skill              # lista turno-spec-review con name/description/location/content
openspec validate c-05-reserva-online-backend --strict
```

Evidencias completas en `docs/skills-mcp/evidencias/`.

# Evidencia — revisión `turno-spec-review` de C-05 (pre-implementación)

- **Fecha**: 2026-11-02
- **Skill aplicada**: `turno-spec-review`, siguiendo el procedimiento de `.opencode/skills/turno-spec-review/SKILL.md`. La sesión arrancó antes de crear la skill, así que la invocación por la herramienta se verificó aparte en un proceso nuevo (`05-invocacion-sesion-nueva.md`).
- **Change**: `openspec/changes/c-05-reserva-online-backend/`
- **Modo**: solo lectura. No se modificó ningún artefacto del change ni código; no se hicieron commits.

## Artefactos y fuentes revisadas

| Tipo | Ruta |
|---|---|
| Change | `openspec/changes/c-05-reserva-online-backend/proposal.md` |
| Change | `openspec/changes/c-05-reserva-online-backend/design.md` |
| Change | `openspec/changes/c-05-reserva-online-backend/tasks.md` |
| Spec delta | `openspec/changes/c-05-reserva-online-backend/specs/reserva-online/spec.md` |
| KB | `knowledge-base/04_modelo_de_datos.md` §Paciente, §Turno, §Notificacion, §AuditoriaTurno |
| KB | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01..07, §RN-AG-01..03, §RN-NO-01..03, §RN-PA-01..02, §RN-AU-01..03 |
| KB | `knowledge-base/06_funcionalidades.md` §US-003, §US-004, §US-009 |
| KB | `knowledge-base/07_flujos_principales.md` §Flujo 1, §Flujo 4 |
| KB | `knowledge-base/10_preguntas_abiertas.md` §PB-01, §PB-02, §PB-03, §PB-04 |
| Roadmap | `CHANGES.md` §C-05 (líneas 163-178) |
| Reglas duras | `AGENTS.md` reglas 1-12 (líneas 94-105) |
| Spec base | `openspec/specs/turno-lifecycle/spec.md` |
| Código | `backend/app/main.py` |
| Código | `backend/app/core/ratelimit.py` |
| Código | `backend/app/modules/agenda/slot_service.py` |
| Código | `backend/app/modules/agenda/public.py` |
| Código | `backend/app/modules/agenda/router.py` |
| Código | `backend/app/modules/turnos/router.py` |
| Código | `backend/app/models/{turno,paciente,notificacion,auditoria,profesional}.py` |
| Código | `backend/alembic/versions/001_core_models.py` |
| Dependencia | paquete instalado `psycopg` 3.3.4 |

**Inventario**: 9 `### Requirement:` y 26 `#### Scenario:` en `specs/reserva-online/spec.md`. No hay artefactos faltantes del change.

## Reglas aplicables extraídas (sin parafrasear umbrales)

- `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01: cinco obligatorios, mail obligatorio con formato válido, 400 en ese campo; confirmación + recordatorios siempre encolados.
- §RN-TU-02: duración default 30, personalizable por turno y por profesional.
- §RN-TU-03: sin dos turnos activos superpuestos; garantía por `SELECT FOR UPDATE` del slot o EXCLUDE Postgres; slot ocupado → 409 + alternativos del mismo día.
- §RN-TU-05: slots = ventanas − bloqueos − turnos activos.
- §RN-TU-06: `token_cancelacion` es la única credencial; sin DNI+teléfono ni "mis turnos".
- §RN-AG-01: sin ventana no hay slots.
- §RN-AG-02: granularidad = `duracion_default_min`.
- §RN-NO-01: confirmación inmediata siempre; recordatorios 24h/2h si la anticipación lo permite.
- §RN-NO-02: envío asincrónico, 3 reintentos con backoff, fallo no bloquea la reserva.
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
| H-01 | ambigüedad | `design.md` §D-2 (línea 37) | `AGENTS.md` regla dura 2 (línea 95) / `knowledge-base/05_reglas_de_negocio.md` §RN-TU-03 | D-2 decide explícitamente **no** usar `SELECT FOR UPDATE` y confiar solo en el EXCLUDE. La regla dura 2 exige "EXCLUDE USING gist + SELECT FOR UPDATE en reserva"; `AGENTS.md` dispone que ante conflicto KB vs. reglas duras prevalecen las reglas duras. | Agregar un lock en la transacción de reserva (por ejemplo `SELECT ... FOR UPDATE` sobre la fila del profesional o un advisory lock) antes de la pre-validación/insert, o dejar un waiver explícito del dueño que actualice la regla dura; reflejarlo en design, spec y tasks. | bloqueante |
| H-02 | borde faltante | `specs/reserva-online/spec.md` §Requirement: Validación estricta... (líneas 55-57) y §Scenario: Faltan campos... (59-63) | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01 / `AGENTS.md` regla dura 1 | El requisito exige "require" los cinco campos, pero no define si un string vacío o solo espacios cuenta como faltante. Un body con `paciente.nombre=""` podría pasar la obligatoriedad y crear turno; no hay escenario que lo pruebe. | Exigir valor no vacío después de `trim` para nombre, DNI, teléfono, obra social y mail; devolver 400 por campo y agregar escenario con `nombre=""` o `"   "`. | mayor |
| H-03 | borde faltante | `specs/reserva-online/spec.md` §Scenario: Campo extra responde 400... (71-75) / `tasks.md` §1.2 | `AGENTS.md` regla dura 1 | El único escenario de campo extra es `paciente.alergias` (nivel anidado). No se verifica que `TurnoCreate` rechace un campo desconocido en el nivel raíz (por ejemplo `notas` o `foo`), aunque la regla dura 1 aplica a todos los schemas. | Agregar escenario de campo extra raíz con `campo="notas"` (o similar), 400 y sin fila `turno`; sumarlo a la tarea 1.2. | mayor |
| H-04 | borde faltante | `specs/reserva-online/spec.md` §Requirement: Duración consistente... (89-91) y §Scenario: duracion_min no múltiplo... (93-97) | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-02 / §RN-AG-02 | El requisito dice "positive multiple", pero no hay escenario para `duracion_min=0` ni negativo. Solo se prueba el no múltiplo (`40` con default `30`); el borde de valor no positivo queda sin resultado observable. | Agregar escenarios parametrizados `duracion_min=0` y `duracion_min=-30` → 400 con `campo="duracion_min"` y sin fila `turno`; cubrirlo en la tarea 1.4. | mayor |
| H-05 | borde faltante | `specs/reserva-online/spec.md` §Requirement: Revalidación del slot... (105-107) y §Scenario: Reserva en el borde de la ventana... (115-119) | `knowledge-base/05_reglas_de_negocio.md` §RN-AG-02 / §RN-TU-05 | No se define ni se prueba qué pasa si `inicio` no está alineado a la grilla del profesional (por ejemplo `09:15` con `duracion_default_min=30`). "fully covered by free slots" es ambiguo; el design D-5/D-6 afirma 409, pero la spec no lo declara. Además, la tarea 3.4 agrega "si el segundo slot está ocupado → 409", comportamiento que no tiene escenario en la spec. | Declarar explícitamente que un `inicio` no alineado se rechaza con 409 de disponibilidad y agregar el escenario; sumar a la spec el caso de bloque contiguo con segundo slot ocupado que ya introduce la tarea 3.4. | mayor |
| H-06 | ambigüedad | `specs/reserva-online/spec.md` §Requirement: Revalidación del slot... (105-107) y §Scenario: Alternativos son del mismo día... (121-125) | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-03 | Los alternativos se describen como "slots libres" sin fijar su duración. Si se pidió `duracion_min=60`, un alternativo de 30 minutos no es reservable y el cliente no puede usarlo; la spec no permite verificarlo. El design D-6 sí dice que son bloques de `duracion_min`, pero la spec no lo refleja. | Definir en la spec que los alternativos son bloques de la `duracion_min` pedida (o del default si se omitió), con el mismo criterio de alineación; agregar la aserción al escenario de alternativos. | mayor |
| H-07 | borde faltante | `specs/reserva-online/spec.md` §Scenario: Reserva con anticipación mayor a 24h... (31-35) y §Scenario: ... menor a 24h... (37-41) | `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01 | No se cubre la anticipación menor a 2 horas (debería quedar solo `confirmacion`) ni los bordes exactos `= 24h` y `= 2h`. La spec usa "más de" y "menos de", pero no define qué pasa en la igualdad; el design D-7 usa comparación estricta `>`, que no está reflejada en la spec. | Fijar las comparaciones exactas (por ejemplo `inicio - 24h > now` y `inicio - 2h > now`) y agregar escenarios para `<2h`, `=24h` y `=2h` con la cantidad de notificaciones esperada; cubrirlo en la tarea 2.4. | mayor |
| H-08 | escenario no verificable | `specs/reserva-online/spec.md` §Requirement: Rate limit... (165-167) y §Scenario: Exceso de reservas por IP... (169-173) | `knowledge-base/05_reglas_de_negocio.md` §RN-AU-03 | La spec no fija el límite ni la ventana. El escenario dice "una IP que ya consumió el límite de reservas de la ventana": es circular y no permite verificar el número exacto (el 10/min y 60 s solo están en design D-9). Tampoco define el valor de `Retry-After` ni si el request 10 pasa y el 11 falla. | Fijar en la spec el límite y la ventana (10 req/60 s/IP, D-9) o referenciarlos explícitamente; agregar escenario de borde "la reserva número 10 pasa y la 11 responde 429". | mayor |
| H-09 | borde faltante | `specs/reserva-online/spec.md` §Scenario: Slot ocupado responde 409... (137-141) y §Scenario: Colisión concurrente... (143-147) / `tasks.md` §3.3, §3.6 | `knowledge-base/05_reglas_de_negocio.md` §RN-PA-02 / §RN-TU-03 | En el 409 se verifica que no aumente el conteo de turnos, pero no que no quede un `Paciente` creado o actualizado por el upsert previo. En la colisión concurrente, el design D-12 prevé revertir toda la transacción para no dejar un paciente huérfano, pero la spec no lo exige ni la tarea 3.6 lo verifica. | Agregar a los escenarios 409 la aserción "no se crea ni actualiza `paciente`" (o "una sola fila de paciente si ya existía") y tests en 3.3/3.6. | mayor |
| H-10 | regla no trazable | `design.md` §D-3 (43-46); spec sin escenario equivalente | `knowledge-base/10_preguntas_abiertas.md` §PB-04 / `AGENTS.md` regla dura 3 | D-3 decide que si el `Paciente` existente está `activo=false` la reserva procede y no se reactiva. Es una decisión de diseño sin RN que la respalde, no está en la spec y no tiene escenario; queda como regla no trazable / open question encubierta. | Convertirla en requisito y escenario explícito (reserva con paciente inactivo: 201, no reactiva, actualiza o no contacto) o moverla formalmente a Open Questions con decisión del dueño; agregar test. | mayor |
| H-11 | ambigüedad | `design.md` §D-7 (67-73) y §D-8 (78-80); `specs/reserva-online/spec.md` §Scenario anticipación >24h (31-35) y §Scenario auditoría (43-47) | `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01 / §RN-AU-02 | `payload.enviar_en`, `payload.inicio`, `payload.fin` y `detalle.inicio`/`detalle.fin` son datetimes que se guardan en columnas JSONB, pero no se define su serialización (ISO-8601 string, epoch, etc.). `payload` y `detalle` son JSONB NOT NULL; SQLAlchemy serializa con `json.dumps` y un `datetime` crudo no es serializable, lo que puede hacer fallar el encolado o la auditoría. | Definir el contrato JSON: datetimes como strings ISO-8601 UTC (o encoder explícito), documentarlo en D-7/D-8 y en la tarea 4.3, y agregar una aserción de tipo/forma en los tests. | mayor |
| H-12 | ambigüedad | `specs/reserva-online/spec.md` §Scenario: Reserva devuelve token y link... (49-53) / `design.md` §D-11 | `knowledge-base/05_reglas_de_negocio.md` §RN-TU-06 | La spec formula `cancel_url` como `FRONTEND_URL + "/cancelar?token=" + token`; el design D-11 usa `FRONTEND_URL.rstrip("/")`. Si `FRONTEND_URL` termina en `/`, la spec produce `//cancelar` y el contrato queda ambiguo. | Fijar la normalización de la base URL (sin barra final) y el formato exacto en la spec; agregar aserción en el escenario. | menor |
| H-13 | ambigüedad | `specs/reserva-online/spec.md` §Scenario: Reserva devuelve token y link... (49-53); `design.md` §D-11 y §D-7 | `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01 | El design D-11 incluye `notificaciones_encoladas` en la respuesta 201, pero la lista de campos del escenario de la spec no lo menciona; solo se verifica ese dato en la auditoría (R6). El contrato de respuesta queda desalineado entre design y spec. | Alinear la spec con D-11 (agregar `notificaciones_encoladas` a la respuesta) o quitarlo del design; si se mantiene, agregar aserción en el escenario de reserva válida. | menor |
| H-14 | ambigüedad | `AGENTS.md` regla dura 5 (línea 98) vs. `design.md` §D-7 y `specs/reserva-online/spec.md` §Scenario: ... menor a 24h... (37-41) | `AGENTS.md` regla dura 5 / `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01 | La regla dura 5 dice "notificaciones condicionales" y "confirmacion+recordatorios siempre encolados", mientras RN-NO-01, PB-02, la spec y D-7 condicionan los recordatorios a la anticipación. La redacción de la regla dura es ambigua y puede leerse como prohibición de toda condición. | Aclarar en la regla dura 5 que "condicional" se refiere al fallback por falta de mail, no a la anticipación; o ajustar la spec/design si la intención es encolar siempre los tres tipos. Registrar la interpretación en el change. | menor |

**Conteo por severidad**: bloqueante 1; mayor 10; menor 3. Total 14.

## Verificación contra el código

| # | Comprobación | Resultado | Evidencia |
|---|---|---|---|
| 1 | Handler global `RequestValidationError → 400`: valor exacto de `campo` para un body anidado y existencia de `parse_body_or_400` | **FALSO** | `backend/app/main.py:56` arma `campo` con `".".join(str(p) for p in e["loc"])`. FastAPI incluye `"body"` en el `loc` de un body, así que un error en `paciente.email` produce `campo="body.paciente.email"`, no `"paciente.email"` como exige la spec. `parse_body_or_400` **no existe en el repo**: solo aparece en `design.md:50` y `tasks.md:11` (grep sin coincidencias en `backend/`). La tarea 1.3 debe crearlo y quitar el prefijo `body`; hoy el contrato de la spec no se cumple con el handler global solo. |
| 2 | `check_public_rate_limit`: firma, reloj inyectable, claves de C-04 y colisión con `turnos-publico:{ip}` | **OK** | `backend/app/core/ratelimit.py:62-68`: `check_public_rate_limit(key, *, now=None, limit=30, window_s=60) -> tuple[bool, float]`; `now` es inyectable, `limit` y `window_s` son keyword-only y el retorno es `(pasa, retry_after_s)`. C-04 usa la clave `agenda-publica:{ip}` en `backend/app/modules/agenda/public.py:41`; `turnos-publico:{ip}` es distinta y no colisiona. `reset_public()` existe en `ratelimit.py:83-85`; `reset()` también limpia `_public` (`ratelimit.py:44-47`). El design debe llamar con argumentos por nombre y desempaquetar la tupla. |
| 3 | `slot_service` y `agenda/public.py`: ¿slots puntuales o rangos? ¿se pueden calcular alternativos de un bloque de `duracion_min` sin duplicar lógica? | **OK** | `backend/app/modules/agenda/slot_service.py:71-114` `compute_slots()` devuelve `list[Slot]` de slots puntuales (dataclass `Slot`, líneas 53-63), no rangos agregados. Los fetchers reales son `fetch_ventanas()` (120), `fetch_bloqueos()` (151) y `fetch_turnos_activos()` (173); los tipos son `Ventana` (27), `BloqueoRango` (38) y `TurnoOcupado` (46). Se pueden calcular alternativos reutilizando `compute_slots()` sin duplicar la semántica `[)`: llamándolo con `duracion_min=pedido` se obtienen bloques ya alineados al inicio de ventana; para aceptar un bloque que empieza en un offset de la grilla default (por ejemplo 09:30 con default 30 y pedido 60) hay que computar con el default y agrupar slots contiguos, que es el helper que describe D-6. No existe hoy una función de agrupación ni de rangos; es lógica nueva pequeña, no una segunda fuente de cómputo. |
| 4 | Modelos y migración: `ux_turno_token`, `ck_turno_duracion_min`, `no_solape_prof`, `actor_id` nullable, `payload` JSONB y enums con los valores usados | **OK** | `backend/app/models/turno.py:60-63` define `ck_turno_duracion_min`; `turno.py:65` define `ux_turno_token`; `backend/alembic/versions/001_core_models.py:40-42` define `no_solape_prof` como EXCLUDE con `estado IN ('reservado','confirmado')`; `auditoria.py:22` deja `actor_id` nullable; `notificacion.py:67` declara `payload` JSONB NOT NULL; `notificacion.py:15-29` define `NotifTipo` (`confirmacion`, `recordatorio_24h`, `recordatorio_2h`, `cancelacion`) y `NotifEstado` (`pendiente`, `enviada`, `fallida`); `001_core_models.py:291-305` crea los enums `notif_tipo` y `notif_estado` con esos valores; `canal` es `mail` (`turno.py:43-46`, migración 165 y 287). `Paciente.dni` es único por `ux_paciente_dni` (`paciente.py:27`). |
| 5 | `psycopg` v3: disponibilidad de `exc.orig.diag.constraint_name` | **OK** | Entorno local: `psycopg` 3.3.4 (`pip show psycopg`). El paquete instalado expone `Error.diag` en `C:\Users\ciroc\AppData\Roaming\Python\Python314\site-packages\psycopg\errors.py:302` y `Diagnostic.constraint_name` en `errors.py:496-497`. SQLAlchemy entrega la excepción DBAPI original en `.orig`, por lo que `exc.orig.diag.constraint_name` es válido para psycopg 3. Caveat: se verificó contra la instalación local (Python 3.14); el runtime fija `psycopg[binary]>=3.0` (`backend/requirements.txt`) y no se ejecutó una conexión real. El fallback textual de D-2 sigue siendo razonable para otros drivers. |
| 6 | Trazabilidad escenario ↔ tarea | **FALSO** | Los 26 `#### Scenario:` tienen al menos una tarea asociada, pero hay tareas sin escenario: 1.1 (verificación de migración), 1.3 (implementación de schemas/helper, soporte de R2), 4.3 (documentación del payload D-7), 5.1-5.5 (integración, regresión y cierre). Además, la tarea 3.4 introduce la aserción "si el segundo slot está ocupado → 409" que no existe como escenario en la spec, y los comportamientos de H-02, H-04, H-05, H-07, H-09 y H-10 no tienen escenario ni tarea de verificación. Detalle en la sección siguiente. |

## Trazabilidad escenario → tarea

### Escenarios sin tarea de verificación

Ninguno de los 26 escenarios queda sin tarea. El mapeo es:

| Escenario | Tarea |
|---|---|
| R1 S1 Reserva válida 201 | 2.1 |
| R1 S2 Sin `duracion_min` usa default | 2.2 |
| R1 S3 DNI existente actualiza contacto | 2.3 |
| R1 S4 Anticipación >24h encola tres | 2.4 |
| R1 S5 Anticipación 2-24h omite 24h | 2.4 |
| R1 S6 Auditoría append-only | 2.5 |
| R1 S7 Token y `cancel_url` | 2.6 |
| R2 S1 Faltantes 400 por campo | 1.2 |
| R2 S2 Mail inválido 400 solo email | 1.2 |
| R2 S3 Campo extra 400 | 1.2 |
| R2 S4 Inicio no futuro 400 | 1.4 |
| R2 S5 Inicio sin zona 400 | 1.2 |
| R3 S1 Duración no múltiplo 400 | 1.4 |
| R3 S2 Duración múltiplo bloque contiguo | 3.4 |
| R4 S1 Fuera de ventana o bloqueado 409 | 3.1 |
| R4 S2 Borde de ventana aceptado | 3.2 |
| R4 S3 Alternativos mismo día | 3.1 |
| R4 S4 Turno cancelado no bloquea | 3.2 |
| R5 S1 Slot ocupado 409 | 3.3 |
| R5 S2 Colisión concurrente un ganador | 3.6 |
| R6 S1 Fallo de encolado no bloquea | 4.1 |
| R6 S2 Notificaciones pendientes | 2.4 |
| R7 S1 Rate limit 429 | 4.2 |
| R8 S1 Profesional inexistente/inactivo 404 | 3.5 |
| R9 S1 Dos tokens distintos | 2.6 |
| R9 S2 Sin login ni DNI+teléfono | 2.6 |

### Tareas que no mapean a un escenario

- 1.1: verificación de que no hace falta migración (proceso, no escenario).
- 1.3: implementación de schemas y `parse_body_or_400` (soporte de R2; no es una verificación de escenario).
- 4.3: documentación del contrato `Notificacion.payload` (D-7; no hay escenario de forma del payload).
- 5.1-5.5: integración, regresión, alcance, validación OpenSpec y cierre (proceso).
- 3.4: además de R3 S2, introduce "si el segundo slot está ocupado → 409", comportamiento ausente de la spec.

### Comportamientos de requisito sin escenario ni tarea

- H-02: valores vacíos o solo espacios en los cinco campos.
- H-03: campo extra en el nivel raíz del body.
- H-04: `duracion_min=0` o negativo.
- H-05: `inicio` no alineado a la grilla del profesional; bloque contiguo con segundo slot ocupado.
- H-07: anticipación `<2h`, `=24h`, `=2h`.
- H-09: no crear/actualizar `Paciente` cuando el 409 ocurre por colisión concurrente.
- H-10: reserva con `Paciente.activo=false`.

## Escenarios por tipo

- **Feliz**: 8
- **Error de negocio**: 9
- **Borde**: 9
- **Total**: 26

Distribución por requisito: R1 tiene 7 (4 feliz, 3 borde), R2 tiene 5 (4 error, 1 borde), R3 tiene 2 (1 feliz, 1 error), R4 tiene 4 (1 error, 3 borde), R5 tiene 2 (1 error, 1 borde), R6 tiene 2 (1 feliz, 1 borde), R7 tiene 1 (error), R8 tiene 1 (error), R9 tiene 2 (feliz). Ningún requisito cubre por sí solo las tres categorías feliz/error/borde; solo R1, R2 y R4 superan los tres escenarios totales.

## Veredicto

**NO LISTO**

Motivo: hay 1 hallazgo bloqueante (H-01: el design omite el `SELECT FOR UPDATE` que exige la regla dura 2 y confía solo en el EXCLUDE) y 6 de los 9 requisitos tienen menos de 3 escenarios (R3, R5, R6, R7, R8 y R9); además, ningún requisito cubre las tres categorías (feliz, error de negocio y borde) dentro de su propio bloque y quedan bordes del checklist sin escenario verificable (H-02, H-04, H-05, H-07, H-09, H-10). No se modificó ningún artefacto del change ni código.

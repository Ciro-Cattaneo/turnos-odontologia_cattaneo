# Tasks — c-06-cancelacion-paciente-backend

> Orden TDD: primero el test que falla, después la implementación mínima, después refactor. Los tests de persistencia corren contra Postgres real (`db_session`/`test_engine` del `conftest`); los mocks se limitan a bordes (reloj inyectable, fallo simulado del insert de encolado). Datos ficticios `.test`, DNI sintéticos y tokens aleatorios (regla dura 12). Sin commit (regla dura 11). **Ninguna tarea está tildada en este propose.**
>
> **Migración: no se requiere.** `001_core_models` ya trae `turno.estado`, `token_cancelacion` (`ux_turno_token`), `updated_at`, `notificacion` con `notif_tipo.cancelacion`, `auditoria_turno` e índices. La tarea 7.1 lo verifica y documenta que C-06 no toca `backend/alembic/versions/` ni `backend/app/models/`.

## 1. Contrato, query estricta y configuración (API/schemas/config)

- [x] 1.1 Escribir en rojo `test_cancelacion_query_token_repetido_400` (R3 S4) y `test_cancelacion_query_dni_telefono_400` (R3 S2) en `backend/tests/test_cancelacion_paciente.py`; implementar el parseo manual de query que acepta solo `token`, rechaza claves extra y token repetido con `400` por campo; correr `pytest backend/tests/test_cancelacion_paciente.py -q` y confirmar verde — capa: API/contrato.
- [x] 1.2 Escribir en rojo y hacer verde `test_cancelacion_respuesta_solo_campos_declarados` (R7 S1) y `test_cancelacion_out_extra_forbid` (R7 S3) con un `CancelacionOut` (`extra="forbid"`) que solo expone `id`, `estado`, `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas` y `mensaje`, sin nombre/DNI/teléfono/email/token — capa: unit/schemas.
- [x] 1.3 Agregar `CONSULTORIO_CONTACTO` opcional (default no secreto) a `app/core/config.py` y a `.env.example`; escribir en rojo y hacer verde `test_cancelacion_contacto_default_y_env` que verifica el default y el override por entorno — capa: unit/config.
- [x] 1.4 Escribir en rojo y hacer verde `test_cancelacion_inicio_iso_utc_en_respuesta` (R7 S1) usando un turno con `inicio`/`fin` en UTC y verificando strings ISO-8601 UTC en el cuerpo `200` — capa: API/serialización.

## 2. Servicio de cancelación y transacción (DB real)

- [x] 2.1 Escribir en rojo y hacer verde `test_cancelacion_mas_de_3h_cancela_y_libera_slot` (R1 S1) con turno `reservado` a más de 3 h, token válido y `slot_service` verificando que el slot vuelve a estar libre; comprobar `200`, `estado=cancelado` y que una nueva reserva del mismo horario responde `201` — capa: DB real/API.
- [x] 2.2 Escribir en rojo y hacer verde `test_cancelacion_turno_confirmado_cancela_200` (R1 S2; `confirmado → cancelado`) — capa: DB real/API.
- [x] 2.3 Escribir en rojo y hacer verde `test_cancelacion_exactamente_3h_acepta_200` (R1 S3; reloj fijo y `inicio = now + 3 h` exacto, borde `>=`) — capa: DB real/servicio.
- [x] 2.4 Escribir en rojo y hacer verde `test_cancelacion_menos_de_3h_422_con_contacto` (R1 S4; `inicio = now + 2 h 59 min`, `detail.codigo="cancelacion_fuera_de_plazo"`, `detail.contacto` no vacío, sin cambios ni mail ni auditoría) — capa: DB real/API.
- [x] 2.5 Escribir en rojo y hacer verde `test_cancelacion_ventana_expirada_422_no_403` (R1 S5; `inicio < now`, token válido → `422` fuera de plazo, no `403`) — capa: DB real/API.
- [x] 2.6 Escribir en rojo y hacer verde `test_cancelacion_umbral_configurable_5h_422` (R1 S6; `CANCEL_HOURS_MIN=5`, `inicio = now + 4 h` → `422`) con `monkeypatch` de settings o provider de umbral — capa: DB real/servicio.
- [x] 2.7 Escribir en rojo y hacer verde `test_cancelacion_no_elimina_fila_turno` (R1 S7; la fila sigue existiendo con `estado=cancelado` y no hay `DELETE` físico) — capa: DB real/servicio.
- [x] 2.8 Implementar `cancellation_service.cancelar()` con el orden transaccional de D-4: `SELECT ... FOR UPDATE` por `id`+`token`, chequeo de estado, regla temporal, `estado=cancelado`, encolado en savepoint, auditoría y commit; verificar que 2.1–2.7 quedan verdes — capa: DB real/servicio.
- [x] 2.9 Escribir en rojo y hacer verde `test_cancelacion_dos_concurrentes_un_solo_efecto` (R4 S4) con dos sesiones/transacciones reales sobre el mismo turno: una transición, un mail y una auditoría; la segunda responde `422 turno_ya_cancelado`, no `500` — capa: DB real/concurrencia.

## 3. Endpoint, credencial única y 403 genérico (API)

- [x] 3.1 Escribir en rojo y hacer verde `test_cancelacion_token_invalido_403` (R2 S2; token bien formado que no corresponde a ningún turno → `403` genérico, sin efectos) — capa: API.
- [x] 3.2 Escribir en rojo y hacer verde `test_cancelacion_token_ausente_vacio_malformado_403` (R2 S3; parametrizado sin token, `token=` y `token=no-es-uuid`) — capa: API.
- [x] 3.3 Escribir en rojo y hacer verde `test_cancelacion_token_de_otro_turno_403` (R2 S4; token del turno A contra el turno B) — capa: API/DB real.
- [x] 3.4 Escribir en rojo y hacer verde `test_cancelacion_id_inexistente_403` y `test_cancelacion_id_malformado_403` (R2 S5; UUID no existente o id que no parsea, mismo `403` genérico) — capa: API.
- [x] 3.5 Escribir en rojo y hacer verde `test_cancelacion_token_en_body_no_autentica_403` (R3 S3; body con token pero query sin `token`) — capa: API.
- [x] 3.6 Implementar la ruta `DELETE /api/turnos/{id}` en `backend/app/modules/turnos/router.py` con `id: str`, parseo defensivo de `id`/`token`, traducción de errores del servicio a `403` genérico, `400` por query extra y `422`/`429` según contrato; verificar 3.1–3.5 y 1.1 verdes — capa: API.
- [x] 3.7 Escribir en rojo y hacer verde `test_cancelacion_turno_cancelado_422_sin_efectos` (R4 S2; segunda llamada con mismo token → `422 turno_ya_cancelado`, sin cambiar `updated_at`, sin segundo mail ni segunda auditoría) — capa: DB real/API.
- [x] 3.8 Escribir en rojo y hacer verde `test_cancelacion_turno_atendido_o_ausente_422` (R4 S3; parametrizado `atendido`/`ausente` → `422 turno_no_cancelable`, estado sin cambios) — capa: DB real/API.
- [x] 3.9 Escribir en rojo y hacer verde `test_cancelacion_403_no_revela_datos_ni_existencia` (R7 S2; el cuerpo del `403` es idéntico para turno existente y para id inexistente) — capa: API.

## 4. Notificación de cancelación (DB real)

- [x] 4.1 Escribir en rojo y hacer verde `test_cancelacion_encola_mail_cancelacion_pendiente` (R5 S1; exactamente una `Notificacion cancelacion`, `canal=mail`, `estado=pendiente`, `intentos=0`, `enviada_at=NULL`, payload con las 11 claves y `enviar_en` ISO-8601 UTC) — capa: DB real/servicio.
- [x] 4.2 Escribir en rojo y hacer verde `test_cancelacion_encolado_falla_no_bloquea_200` (R5 S2; fallo simulado del insert en el borde del servicio, `200`, turno `cancelado`, auditoría y respuesta `notificaciones_encoladas=false`) — capa: DB real/servicio (mock de borde).
- [x] 4.3 Escribir en rojo y hacer verde `test_cancelacion_no_envia_smtp_ni_crea_otra_cola` (R5 S3; la ruta no invoca sender/SMTP y la fila queda `pendiente` para C-08, sin estructura alternativa) — capa: API/DB real.
- [x] 4.4 Documentar en el apply log el contrato de `payload` de `cancelacion` (mismas 11 claves, `enviar_en=now`, timestamps ISO-8601 UTC, sin DNI/teléfono/OS) y el punto de coordinación con C-08 (el worker la envía aunque el turno esté `cancelado`). Tarea de contrato que soporta R5 S1/S3; verificación: lectura del apply log y `grep "cancelacion" backend/tests/test_cancelacion_paciente.py`.

## 5. Auditoría append-only (DB real)

- [x] 5.1 Escribir en rojo y hacer verde `test_cancelacion_escribe_auditoria_actor_paciente` (R6 S1; `accion="cancelar"`, `actor_id=NULL`, `detalle.actor="paciente"`, `detalle.credencial="token_cancelacion"`, `estado_previo`, `inicio`/`fin` ISO-8601 UTC, `notificaciones_encoladas`) — capa: DB real/servicio.
- [x] 5.2 Escribir en rojo y hacer verde `test_cancelacion_400_422_no_escriben_auditoria` (R6 S2; ninguna solicitud rechazada agrega filas a `auditoria_turno`) — capa: DB real/API.
- [x] 5.3 Escribir en rojo y hacer verde `test_cancelacion_auditoria_no_guarda_token` (R6 S3; el token completo no aparece en `detalle` ni en logs capturados) — capa: unit/servicio.

## 6. Rate limit del endpoint público (API/dependencia)

- [x] 6.1 Escribir en rojo y hacer verde `test_cancelacion_rate_limit_dentro_limite_200` (R8 S1; una cancelación dentro de la ventana responde `200` y consume cupo) con `ratelimit.reset_public()` y reloj fijo — capa: API/dependencia.
- [x] 6.2 Escribir en rojo y hacer verde `test_cancelacion_rate_limit_exceso_429_sin_cancelar` (R8 S2; la IP agotada recibe `429` con `Retry-After`, turno sin cambios) — capa: API/dependencia.
- [x] 6.3 Escribir en rojo y hacer verde `test_cancelacion_rate_limit_decimo_pasa_undecimo_429` (R8 S3; el intento 10 se evalúa y el 11 responde `429` antes de evaluar la credencial) — capa: API/dependencia.
- [x] 6.4 Implementar la dependencia de throttle `turnos-cancelacion:{ip}` (10/min, ventana fija 60 s) reutilizando `check_public_rate_limit` y verificar 6.1–6.3 verdes — capa: API/dependencia.

## 7. Integración, regresión y cierre (proceso)

- [x] 7.1 Verificar que no hace falta migración: `Select-String -Path backend/alembic/versions/*.py -Pattern "no_solape_prof|ux_turno_token|notif_tipo|cancelacion"` y `alembic -c backend/alembic.ini current`; documentar que C-06 no toca `backend/alembic/versions/` ni `backend/app/models/`. Verificación: salida de los comandos y `git status --short` sin archivos de migración/modelos — capa: proceso.
- [x] 7.2 Correr `pytest backend/tests/test_cancelacion_paciente.py -q` y `ruff check backend`; todo verde. Tarea de proceso: evidencia de todos los escenarios de `cancelacion-paciente`.
- [x] 7.3 Correr la suite completa `pytest backend/tests -q` y confirmar que no hay regresiones en C-02/C-03/C-04/C-05/C-08. Tarea de proceso: regresión de integración.
- [x] 7.4 Revisar `git status --short` y `git diff --stat`: solo deben aparecer `backend/app/modules/turnos/{router,service,cancellation_service,schemas}.py`, `backend/app/core/config.py`, `.env.example`, tests nuevos y `openspec/changes/c-06-cancelacion-paciente-backend/*`; sin cambios en `backend/app/models/`, `backend/alembic/versions/`, `CHANGES.md`, `AGENTS.md`, `CLAUDE.md`, `README.md` ni `.atl/skill-registry.md`. Tarea de proceso: revisión de alcance.
- [x] 7.5 Correr `openspec validate c-06-cancelacion-paciente-backend --strict` y `openspec status --change c-06-cancelacion-paciente-backend --json`; confirmar artefactos de planificación completos. Tarea de proceso: validación de artefactos.
- [x] 7.6 Cerrar el apply log con las decisiones D-1…D-13, el contrato de payload `cancelacion`, la interpretación de "token expirado" (turno pasado → `422`, token inexistente → `403`) y el valor operativo de `CONSULTORIO_CONTACTO`. Tarea de proceso: trazabilidad del cierre.

## Trazabilidad escenario → tarea

| Requisito | Escenario | Tarea | Test propuesto | Capa |
|---|---|---|---|---|
| R1 | Cancelación con más de 3h libera el slot y responde 200 | 2.1 | `test_cancelacion_mas_de_3h_cancela_y_libera_slot` | DB real/API |
| R1 | Cancelación de un turno confirmado procede igual que reservado | 2.2 | `test_cancelacion_turno_confirmado_cancela_200` | DB real/API |
| R1 | Exactamente 3 horas de anticipación se acepta | 2.3 | `test_cancelacion_exactamente_3h_acepta_200` | DB real/servicio |
| R1 | Cancelación con menos de 3h responde 422 con contacto | 2.4 | `test_cancelacion_menos_de_3h_422_con_contacto` | DB real/API |
| R1 | Ventana de cancelación expirada responde 422 y no 403 | 2.5 | `test_cancelacion_ventana_expirada_422_no_403` | DB real/API |
| R1 | El umbral respeta CANCEL_HOURS_MIN configurado | 2.6 | `test_cancelacion_umbral_configurable_5h_422` | DB real/servicio |
| R1 | La cancelación no elimina la fila del turno | 2.7 | `test_cancelacion_no_elimina_fila_turno` | DB real/servicio |
| R2 | Token válido del turno habilita la cancelación | 2.1 | `test_cancelacion_mas_de_3h_cancela_y_libera_slot` | DB real/API |
| R2 | Token inválido responde 403 genérico sin efectos | 3.1 | `test_cancelacion_token_invalido_403` | API |
| R2 | Token ausente, vacío o mal formado responde 403 genérico | 3.2 | `test_cancelacion_token_ausente_vacio_malformado_403` | API |
| R2 | Token válido de otro turno responde 403 genérico | 3.3 | `test_cancelacion_token_de_otro_turno_403` | API/DB real |
| R2 | Id inexistente o mal formado responde 403 genérico | 3.4 | `test_cancelacion_id_inexistente_403` / `test_cancelacion_id_malformado_403` | API |
| R3 | Solo el token válido por query permite cancelar | 2.1 | `test_cancelacion_mas_de_3h_cancela_y_libera_slot` | DB real/API |
| R3 | DNI y teléfono como query no cancelan el turno | 1.1 | `test_cancelacion_query_dni_telefono_400` | API/contrato |
| R3 | Un token en el body no autentica la cancelación | 3.5 | `test_cancelacion_token_en_body_no_autentica_403` | API |
| R3 | El parámetro token repetido no habilita la cancelación | 1.1 | `test_cancelacion_query_token_repetido_400` | API/contrato |
| R4 | Turno reservado con token válido es cancelable | 2.1 | `test_cancelacion_mas_de_3h_cancela_y_libera_slot` | DB real/API |
| R4 | Turno ya cancelado responde 422 sin efectos laterales | 3.7 | `test_cancelacion_turno_cancelado_422_sin_efectos` | DB real/API |
| R4 | Turno atendido o ausente responde 422 | 3.8 | `test_cancelacion_turno_atendido_o_ausente_422` | DB real/API |
| R4 | Dos cancelaciones concurrentes producen un solo efecto | 2.9 | `test_cancelacion_dos_concurrentes_un_solo_efecto` | DB real/concurrencia |
| R5 | Cancelación exitosa encola un mail cancelacion pendiente | 4.1 | `test_cancelacion_encola_mail_cancelacion_pendiente` | DB real/servicio |
| R5 | Fallo del encolado no deshace la cancelación | 4.2 | `test_cancelacion_encolado_falla_no_bloquea_200` | DB real/servicio |
| R5 | C-06 no envía SMTP ni duplica la cola | 4.3 | `test_cancelacion_no_envia_smtp_ni_crea_otra_cola` | API/DB real |
| R6 | Cancelación escribe auditoría con actor paciente | 5.1 | `test_cancelacion_escribe_auditoria_actor_paciente` | DB real/servicio |
| R6 | Una solicitud rechazada no escribe auditoría | 5.2 | `test_cancelacion_400_422_no_escriben_auditoria` | DB real/API |
| R6 | La auditoría no guarda el token en claro | 5.3 | `test_cancelacion_auditoria_no_guarda_token` | unit/servicio |
| R7 | Respuesta 200 no expone datos del paciente | 1.2 | `test_cancelacion_respuesta_solo_campos_declarados` | unit/schemas |
| R7 | Respuesta 403 no revela existencia ni datos del turno | 3.9 | `test_cancelacion_403_no_revela_datos_ni_existencia` | API |
| R7 | Un campo desconocido en la respuesta es imposible por contrato | 1.2 | `test_cancelacion_out_extra_forbid` | unit/schemas |
| R8 | Cancelación dentro del límite responde 200 | 6.1 | `test_cancelacion_rate_limit_dentro_limite_200` | API/dependencia |
| R8 | Exceso de intentos responde 429 sin cancelar | 6.2 | `test_cancelacion_rate_limit_exceso_429_sin_cancelar` | API/dependencia |
| R8 | El intento 10 pasa y el 11 responde 429 | 6.3 | `test_cancelacion_rate_limit_decimo_pasa_undecimo_429` | API/dependencia |

## Workflow follow-up

- Ejecutar `/opsx:apply c-06-cancelacion-paciente-backend` recién con una orden nueva; este propose no implementa código.
- Después de la revisión con `turno-spec-review` y de que la suite esté verde, ejecutar `/opsx:archive c-06-cancelacion-paciente-backend` y marcar C-06 como completado en `CHANGES.md` (fuera de este paso).
- No commitear ni pushear hasta que el usuario lo pida explícitamente.

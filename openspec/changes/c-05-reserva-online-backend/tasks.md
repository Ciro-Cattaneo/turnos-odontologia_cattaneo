# Tasks — c-05-reserva-online-backend

> Orden TDD: primero el test que falla, después la implementación mínima, después refactor. Los tests de persistencia corren contra Postgres real (`db_session`/`test_engine` del `conftest`); los mocks se limitan a bordes (reloj fake, fallo simulado de encolado, ausencia de SMTP). Datos ficticios `.test` y DNI sintéticos (regla dura 12). Sin commit (regla dura 11).
>
> **Migración: no se requiere.** `001_core_models` ya trae `btree_gist`, `no_solape_prof`, `ck_turno_duracion_min`, `ux_turno_token` y `ux_paciente_dni`; C-05 no agrega columnas ni tablas. La tarea 1.1 lo verifica y lo deja documentado.

## 1. Contrato, schemas y validación por campo (R2, R3)

- [x] 1.1 Verificar que no hace falta migración: `rg "no_solape_prof|ck_turno_duracion_min|ux_turno_token|ux_paciente_dni" backend/alembic/versions/001_core_models.py` y `alembic -c backend/alembic.ini current`; documentar en el apply log que C-05 no toca `backend/alembic/versions/` ni `backend/app/models/`. Tarea de proceso, no mapea a un escenario: es precondición de D-13; verificación: salida de los comandos y `git status --short` sin archivos de migración/modelos.
- [x] 1.2 Escribir en rojo `backend/tests/test_turno_schemas_400.py` con `test_reserva_faltantes_400_por_campo` (R2 S1), `test_reserva_vacios_400_por_campo` (R2 S2, `nombre=""` y `telefono="   "`), `test_reserva_email_invalido_400_solo_email` (R2 S3), `test_reserva_campo_extra_anidado_400` (R2 S4, `paciente.alergias`), `test_reserva_campo_extra_raiz_400` (R2 S5, `notas`) y `test_reserva_inicio_sin_zona_400` (R2 S7); correr `pytest backend/tests/test_turno_schemas_400.py -q` y confirmar rojo — capa: schemas/API.
- [x] 1.3 Implementar `TurnoCreate`/`PacienteIn` con `ConfigDict(extra="forbid")`, exigir los cinco campos no vacíos después de `trim`, email `str` + patrón (sin `EmailStr`, por `.test`), `inicio` con zona obligatoria y el helper `parse_body_or_400` que normaliza `loc` quitando `body`; correr `pytest backend/tests/test_turno_schemas_400.py -q` en verde. Tarea de implementación que soporta R2 (no mapea a un escenario propio); verificación: la suite de 1.2 en verde.
- [x] 1.4 Escribir en rojo y hacer verde `test_reserva_inicio_no_futuro_400` (R2 S6), `test_reserva_duracion_no_multiplo_400` (R3 S1) y `test_reserva_duracion_cero_o_negativa_400` parametrizado con `0` y `-30` (R3 S2) en `backend/tests/test_reserva_online.py`, usando reloj inyectable y profesional con `duracion_default_min=30`; implementar la validación de futuro y de múltiplo positivo sin escribir filas — capa: API/servicio.

## 2. Reserva feliz y persistencia (R1)

- [x] 2.1 Escribir en rojo `test_reserva_valida_crea_turno_201` (R1 S1) en `backend/tests/test_reserva_online.py` (profesional activo, ventana local, reloj fijo, body válido) y hacerlo verde con el servicio `reserva_service.reservar()` y el orden transaccional de D-12; verificar `notificaciones_encoladas=true` en la respuesta — capa: API/DB.
- [x] 2.2 Escribir en rojo y hacer verde `test_reserva_sin_duracion_usa_default_201` (R1 S2; profesional `duracion_default_min=45`, `duracion_min` omitido → `fin=inicio+45`) — capa: API/DB.
- [x] 2.3 Escribir en rojo y hacer verde `test_reserva_dni_existente_actualiza_contacto_sin_duplicar` (R1 S3; mismo DNI, teléfono/mail nuevos, una sola fila `paciente`, `turno.paciente_id` reutilizado) con `INSERT ... ON CONFLICT (dni) DO UPDATE ... RETURNING id` — capa: API/DB.
- [x] 2.4 Escribir en rojo y hacer verde `test_reserva_paciente_inactivo_no_reactiva_201` (R1 S4; `Paciente.activo=false`, la reserva responde `201`, actualiza contacto y deja `activo=false`, sin duplicar fila) — capa: API/DB.
- [x] 2.5 Escribir en rojo y hacer verde `test_reserva_escribe_auditoria_crear` (R1 S5; `accion=crear`, `actor_id=NULL`, `detalle` con `origen`, `profesional_id`, `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas`; `detalle.inicio`/`detalle.fin` son strings ISO-8601 UTC) — capa: DB/servicio.
- [x] 2.6 Escribir en rojo y hacer verde `test_reserva_devuelve_token_y_cancel_url_normalizada` (R1 S6; `FRONTEND_URL` con barra final, `cancel_url` sin doble barra, `token_cancelacion` UUID, `notificaciones_encoladas` en la respuesta) y los tests de credencial R9 `test_reserva_tokens_distintos_por_turno` (dos reservas en slots distintos → tokens distintos), `test_reserva_sin_login_201` (sin cookie/header de auth → 201) y `test_reserva_dni_telefono_raiz_400` (`dni`/`telefono` en la raíz → 400 por campo extra) — capa: API/DB.
- [x] 2.7 Escribir en rojo y hacer verde `test_reserva_anticipacion_mayor_24h_encola_tres` (R1 S7) y `test_reserva_anticipacion_2_a_24h_omite_24h` (R1 S8); verificar cantidad y tipo de filas `notificacion` y `payload.enviar_en` como string ISO-8601 UTC — capa: DB/servicio.

## 3. Disponibilidad, anti-solape y profesional (R3 S3, R4, R5, R8)

- [x] 3.1 Escribir en rojo y hacer verde `test_reserva_duracion_multiplo_bloque_contiguo_201` (R3 S3; dos slots libres consecutivos, `duracion_min=60`, `fin=inicio+60`) — capa: API/DB.
- [x] 3.2 Escribir en rojo y hacer verde `test_reserva_slot_fuera_ventana_409_alternativos` y `test_reserva_slot_bloqueado_409_alternativos` (R4 S1; `detail.codigo="slot_no_disponible"`, alternativos del mismo día, sin `turno` ni `paciente`) — capa: API/servicio.
- [x] 3.3 Escribir en rojo y hacer verde `test_reserva_inicio_no_alineado_409` (R4 S2; `inicio=09:15` con default 30 → `409` `slot_no_disponible`, alternativos alineados, sin filas) — capa: API/servicio.
- [x] 3.4 Escribir en rojo y hacer verde `test_reserva_bloque_contiguo_segundo_slot_ocupado_409` (R4 S3; primer slot libre, segundo ocupado, `duracion_min=60` → `409`, sin filas) — capa: API/DB.
- [x] 3.5 Escribir en rojo y hacer verde `test_reserva_borde_ventana_fin_hasta_201` (R4 S4; semántica half-open `[)`, `fin=hora_hasta`) — capa: API/DB.
- [x] 3.6 Escribir en rojo y hacer verde `test_reserva_alternativos_mismo_dia_duracion_pedida` (R4 S5; misma fecha local, excluye el `inicio` pedido, orden ascendente, máximo cinco, `fin=inicio+duracion_min` pedida y alineados a la grilla) — capa: API/servicio.
- [x] 3.7 Escribir en rojo y hacer verde `test_reserva_turno_cancelado_no_bloquea_201` (R4 S6; solo estados `reservado`/`confirmado` ocupan slot) — capa: API/DB.
- [x] 3.8 Escribir en rojo y hacer verde `test_reserva_slot_ocupado_409_con_alternativos` (R5 S1; turno activo preexistente, `detail.codigo="slot_ocupado"`, conteo de turnos sin aumentar, sin crear/actualizar `paciente`) — capa: API/DB.
- [x] 3.9 Escribir en rojo y hacer verde `test_reserva_segunda_transaccion_espera_lock_409` (R5 S2; dos sesiones/transacciones reales sobre el mismo profesional; la segunda espera el `SELECT ... FOR UPDATE`, la primera commitea y la segunda responde `409`, no `500`; queda una sola fila activa y ningún paciente huérfano) — capa: DB/servicio (concurrencia real).
- [x] 3.10 Escribir en rojo y hacer verde `test_reserva_exclude_autoridad_final_409` (R5 S3; escritura concurrente que no toma el lock, `IntegrityError(no_solape_prof)` mapeado a `409` con alternativos, sin `500` y sin segunda fila activa; se revierte el upsert de paciente) — capa: DB/servicio (concurrencia real).
- [x] 3.11 Escribir en rojo y hacer verde `test_reserva_contigua_no_solapa_201` (R5 S4; turno activo que termina justo cuando empieza el pedido → `201`, dos filas activas contiguas) — capa: API/DB.
- [x] 3.12 Escribir en rojo y hacer verde `test_reserva_profesional_inexistente_404` (R8 S1), `test_reserva_profesional_inactivo_404` (R8 S2) y `test_reserva_profesional_activo_201` (R8 S3), parametrizados donde comparten body; sin crear `turno` ni `paciente` en los 404 — capa: API/DB.

## 4. Notificaciones no bloqueantes y contrato del payload (R6)

- [x] 4.1 Escribir en rojo y hacer verde `test_reserva_encolado_falla_no_bloquea_201` (R6 S1; fallo simulado del insert de `Notificacion` en el borde del servicio; `201`, `turno` + `auditoria_turno` persistidos, `detalle.notificaciones_encoladas=false` y respuesta `notificaciones_encoladas=false`) — capa: API/servicio (mock de borde).
- [x] 4.2 Escribir en rojo y hacer verde `test_reserva_notificaciones_pendientes_para_worker` (R6 S2; `estado=pendiente`, `intentos=0`, `enviada_at=NULL`, sin SMTP, `payload.enviar_en` string ISO-8601 UTC) — capa: DB/servicio.
- [x] 4.3 Escribir en rojo y hacer verde `test_reserva_anticipacion_menor_2h_solo_confirmacion` (R6 S3; solo `confirmacion`) — capa: DB/servicio.
- [x] 4.4 Escribir en rojo y hacer verde `test_reserva_anticipacion_exacta_24h_omite_recordatorio_24h` (R6 S4; `inicio - 24h == now` → `confirmacion` + `recordatorio_2h`, sin `recordatorio_24h`) — capa: DB/servicio.
- [x] 4.5 Escribir en rojo y hacer verde `test_reserva_anticipacion_exacta_2h_omite_recordatorio_2h` (R6 S5; `inicio - 2h == now` → solo `confirmacion`) — capa: DB/servicio.
- [x] 4.6 Documentar en el apply log el contrato de `Notificacion.payload` (datetimes como strings ISO-8601 UTC, datos mínimos, sin DNI/teléfono/OS), la interpretación H-14 de “siempre encolados” (sin fallback por falta de mail; recordatorios según anticipación RN-NO-01) y el punto de coordinación con C-08. Tarea de contrato que soporta R6 S2 y R1 S7 (no mapea a un escenario propio); verificación: lectura del apply log y `rg "enviar_en" backend/tests/test_reserva_online.py`.

## 5. Rate limit del endpoint público (R7)

- [x] 5.1 Escribir en rojo y hacer verde `test_reserva_rate_limit_dentro_limite_201` (R7 S1; una reserva dentro de la ventana responde `201` y consume cupo) con reloj fake y `ratelimit.reset_public()` — capa: API/dependencia.
- [x] 5.2 Escribir en rojo y hacer verde `test_reserva_rate_limit_decima_pasa_undecima_429` (R7 S2; 9 consumidas, la 10 responde `201`, la 11 responde `429` con `Retry-After` en segundos hasta el reset y sin crear `turno`) — capa: API/dependencia.
- [x] 5.3 Escribir en rojo y hacer verde `test_reserva_rate_limit_ips_independientes` (R7 S3; IP A agotada, IP B responde `201`) — capa: API/dependencia.

## 6. Integración, regresión y cierre (proceso)

- [x] 6.1 Correr `pytest backend/tests/test_reserva_online.py backend/tests/test_turno_schemas_400.py -q` y `ruff check backend`; todo verde. Tarea de proceso: agrega la evidencia de todos los escenarios de `reserva-online`.
- [x] 6.2 Correr la suite completa `pytest backend/tests -q` y confirmar que no hay regresiones en C-02/C-03/C-04. Tarea de proceso: regresión de integración.
- [x] 6.3 Revisar `git status --short` y `git diff --stat`: solo deben aparecer `backend/app/modules/turnos/*`, tests nuevos, `docs/skills-mcp/evidencias/01-context7-consultas.md` y `openspec/changes/c-05-reserva-online-backend/*`; sin cambios en `backend/app/models/`, `backend/alembic/versions/`, `CHANGES.md`, `AGENTS.md`, `CLAUDE.md`, `README.md` ni `.atl/skill-registry.md`. Tarea de proceso: revisión de alcance.
- [x] 6.4 Correr `openspec validate c-05-reserva-online-backend --strict` y `openspec status --change c-05-reserva-online-backend --json`; confirmar artefactos de planificación completos. Tarea de proceso: validación de artefactos.
- [x] 6.5 Cerrar el apply log con las decisiones D-1…D-13, las dos consultas a Context7 y los puntos abiertos (contrato de payload con C-08, límite exacto de rate limit); incluir la interpretación H-14 y la decisión cerrada de paciente inactivo. Tarea de proceso: trazabilidad del cierre.

## Trazabilidad escenario → tarea

| Requisito | Escenario | Tarea | Test propuesto | Capa |
|---|---|---|---|---|
| R1 | Reserva válida crea turno reservado y responde 201 | 2.1 | `test_reserva_valida_crea_turno_201` | API/DB |
| R1 | Reserva sin duracion_min usa la duración default del profesional | 2.2 | `test_reserva_sin_duracion_usa_default_201` | API/DB |
| R1 | Reserva con DNI existente actualiza contacto sin duplicar paciente | 2.3 | `test_reserva_dni_existente_actualiza_contacto_sin_duplicar` | API/DB |
| R1 | Reserva con paciente inactivo procede sin reactivarlo | 2.4 | `test_reserva_paciente_inactivo_no_reactiva_201` | API/DB |
| R1 | Reserva escribe auditoría append-only con actor paciente | 2.5 | `test_reserva_escribe_auditoria_crear` | DB/servicio |
| R1 | Reserva devuelve token y link de cancelación normalizado | 2.6 | `test_reserva_devuelve_token_y_cancel_url_normalizada` | API/DB |
| R1 | Reserva con anticipación mayor a 24h encola tres notificaciones | 2.7 | `test_reserva_anticipacion_mayor_24h_encola_tres` | DB/servicio |
| R1 | Reserva con anticipación entre 2h y 24h omite el recordatorio de 24h | 2.7 | `test_reserva_anticipacion_2_a_24h_omite_24h` | DB/servicio |
| R2 | Faltan campos obligatorios y responde 400 por campo | 1.2 | `test_reserva_faltantes_400_por_campo` | schemas/API |
| R2 | Campos vacíos o solo espacios se tratan como faltantes | 1.2 | `test_reserva_vacios_400_por_campo` | schemas/API |
| R2 | Mail inválido responde 400 solo en paciente.email | 1.2 | `test_reserva_email_invalido_400_solo_email` | schemas/API |
| R2 | Campo extra anidado responde 400 en ese campo | 1.2 | `test_reserva_campo_extra_anidado_400` | schemas/API |
| R2 | Campo extra en la raíz responde 400 en ese campo | 1.2 | `test_reserva_campo_extra_raiz_400` | schemas/API |
| R2 | inicio no futuro responde 400 en inicio | 1.4 | `test_reserva_inicio_no_futuro_400` | API/servicio |
| R2 | inicio sin zona horaria responde 400 en inicio | 1.2 | `test_reserva_inicio_sin_zona_400` | schemas/API |
| R3 | duracion_min no múltiplo responde 400 y no crea turno | 1.4 | `test_reserva_duracion_no_multiplo_400` | API/servicio |
| R3 | duracion_min cero o negativa responde 400 y no crea turno | 1.4 | `test_reserva_duracion_cero_o_negativa_400` | API/servicio |
| R3 | duracion_min múltiplo reserva un bloque contiguo | 3.1 | `test_reserva_duracion_multiplo_bloque_contiguo_201` | API/DB |
| R4 | Slot fuera de ventana o bloqueado responde 409 con alternativos | 3.2 | `test_reserva_slot_fuera_ventana_409_alternativos` / `test_reserva_slot_bloqueado_409_alternativos` | API/servicio |
| R4 | inicio no alineado a la grilla responde 409 | 3.3 | `test_reserva_inicio_no_alineado_409` | API/servicio |
| R4 | Bloque contiguo con el segundo slot ocupado responde 409 | 3.4 | `test_reserva_bloque_contiguo_segundo_slot_ocupado_409` | API/DB |
| R4 | Reserva en el borde de la ventana es aceptada | 3.5 | `test_reserva_borde_ventana_fin_hasta_201` | API/DB |
| R4 | Alternativos son del mismo día, excluyen el pedido y respetan la duración pedida | 3.6 | `test_reserva_alternativos_mismo_dia_duracion_pedida` | API/servicio |
| R4 | Turno cancelado no bloquea el slot | 3.7 | `test_reserva_turno_cancelado_no_bloquea_201` | API/DB |
| R5 | Slot ocupado responde 409 con alternativos y sin paciente nuevo | 3.8 | `test_reserva_slot_ocupado_409_con_alternativos` | API/DB |
| R5 | La segunda transacción espera el lock del profesional y termina en 409 | 3.9 | `test_reserva_segunda_transaccion_espera_lock_409` | DB/servicio (concurrencia real) |
| R5 | El EXCLUDE es autoridad final ante una escritura fuera del lock | 3.10 | `test_reserva_exclude_autoridad_final_409` | DB/servicio (concurrencia real) |
| R5 | Reservas contiguas no colisionan | 3.11 | `test_reserva_contigua_no_solapa_201` | API/DB |
| R6 | Fallo del encolado no bloquea la reserva | 4.1 | `test_reserva_encolado_falla_no_bloquea_201` | API/servicio (mock de borde) |
| R6 | Notificaciones quedan pendientes para el worker | 4.2 | `test_reserva_notificaciones_pendientes_para_worker` | DB/servicio |
| R6 | Anticipación menor a 2h encola solo la confirmación | 4.3 | `test_reserva_anticipacion_menor_2h_solo_confirmacion` | DB/servicio |
| R6 | Anticipación exactamente 24h omite solo el recordatorio de 24h | 4.4 | `test_reserva_anticipacion_exacta_24h_omite_recordatorio_24h` | DB/servicio |
| R6 | Anticipación exactamente 2h omite el recordatorio de 2h | 4.5 | `test_reserva_anticipacion_exacta_2h_omite_recordatorio_2h` | DB/servicio |
| R7 | Reserva dentro del límite responde 201 y consume cupo | 5.1 | `test_reserva_rate_limit_dentro_limite_201` | API/dependencia |
| R7 | La reserva número 10 pasa y la 11 responde 429 | 5.2 | `test_reserva_rate_limit_decima_pasa_undecima_429` | API/dependencia |
| R7 | IPs distintas no comparten el cupo de reservas | 5.3 | `test_reserva_rate_limit_ips_independientes` | API/dependencia |
| R8 | Profesional inexistente responde 404 | 3.12 | `test_reserva_profesional_inexistente_404` | API/DB |
| R8 | Profesional inactivo responde 404 | 3.12 | `test_reserva_profesional_inactivo_404` | API/DB |
| R8 | Profesional activo con el mismo body responde 201 | 3.12 | `test_reserva_profesional_activo_201` | API/DB |
| R9 | Dos reservas generan tokens distintos | 2.6 | `test_reserva_tokens_distintos_por_turno` | API/DB |
| R9 | La reserva no requiere login | 2.6 | `test_reserva_sin_login_201` | API/DB |
| R9 | DNI y teléfono en la raíz no funcionan como credencial | 2.6 | `test_reserva_dni_telefono_raiz_400` | API/DB |

## Workflow follow-up

- Ejecutar `/opsx:apply c-05-reserva-online-backend` recién con una orden nueva; este propose no implementa código.
- Después de la revisión con `turno-spec-review` y de que la suite esté verde, ejecutar `/opsx:archive c-05-reserva-online-backend` y marcar C-05 como completado en `CHANGES.md` (fuera de este paso).
- No commitear ni pushear hasta que el usuario lo pida explícitamente.

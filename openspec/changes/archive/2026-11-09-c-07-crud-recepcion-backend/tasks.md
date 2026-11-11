# Tasks — c-07-crud-recepcion-backend

> Orden TDD: primero el test que falla, después la implementación mínima, después refactor. Los tests de persistencia corren contra Postgres real (`db_session`/`test_engine` del `conftest`); los mocks se limitan a bordes (reloj inyectable, fallo simulado del insert de encolado). Datos ficticios `.test`, DNI sintéticos y tokens aleatorios (regla dura 12). Sin commit (regla dura 11). **Ninguna tarea está tildada en este propose.**
>
> **Migración: no se requiere.** `001_core_models` ya trae `turno.origen/estado/updated_at`, `token_cancelacion` (`ux_turno_token`), `EXCLUDE no_solape_prof`, `paciente.dni` (`ux_paciente_dni`), `notif_tipo` y `auditoria_turno` con trigger append-only (`auditoria_no_update_delete`) e `ix_auditoria_turno_turno_id`. La tarea 10.1 lo verifica y documenta que C-07 no toca `backend/alembic/versions/` ni `backend/app/models/`.

## 1. Contratos, schemas y despacho por sesión (API/unit)

- [x] 1.1 Escribir en rojo `test_alta_staff_body_incompleto_400_por_campo` (R1 S5), `test_alta_staff_origen_ausente_o_invalido_400` (R1 S10) y `test_alta_staff_respuesta_sin_token` (R1 S2) en `backend/tests/test_turnos_staff.py`; crear `TurnoCreateStaff` y `TurnoStaffOut` en `backend/app/modules/turnos/schemas.py` con `extra="forbid"`, `origen: Literal["recepcion"]` y `notificaciones_encoladas`, sin `token_cancelacion` ni `cancel_url`; implementar hasta verde — capa: unit/schemas.
- [x] 1.2 Escribir en rojo y hacer verde `test_alta_staff_sin_sesion_origen_400_no_regresion` (R1 S3) y `test_alta_staff_sin_sesion_body_publico_sigue_online` (R1 S4): `POST /api/turnos` resuelve `staff_opcional` antes de parsear el body y, sin sesión, usa el contrato público de C-05 sin cambios — capa: API/contrato.
- [x] 1.3 Escribir en rojo y hacer verde `test_alta_staff_odontologo_403` (R1 S5) y `test_alta_staff_recepcion_201_origen_recepcion_actor` (R1 S1): despacho `recepcion`/`admin` → 201 con `origen=recepcion`, `estado=reservado`, token persistido, una sola fila `paciente`, `notificaciones_encoladas=true` y auditoría `crear` con actor staff — capa: DB real/API.
- [x] 1.4 Escribir en rojo y hacer verde `test_alta_staff_slot_ocupado_409_alternativos_sin_paciente` (R1 S7) y `test_alta_staff_profesional_inexistente_o_inactivo_404` (R1 S8), reutilizando la pre-validación de slots y el mapeo de `IntegrityError` de C-05 — capa: DB real/API.
- [x] 1.5 Escribir en rojo y hacer verde `test_alta_staff_encolado_falla_201_notificaciones_false` (R1 S9): fallo simulado del insert de `Notificacion` no revierte turno, paciente ni auditoría — capa: DB real/servicio (mock de borde).
- [x] 1.6 Escribir en rojo y hacer verde `test_reprogramar_body_sin_campos_400` y `test_reprogramar_campo_extra_400` (R2 S10): `TurnoReprogramar` con `inicio`/`duracion_min` opcionales, al menos uno, `extra="forbid"` — capa: unit/schemas.
- [x] 1.7 Escribir en rojo y hacer verde `test_correccion_paciente_body_sin_campos_400` (R4 S6) y `test_correccion_paciente_nombre_email_400` (R4 S7): `CorreccionPacienteIn` solo con `dni`/`telefono`/`obra_social`, `extra="forbid"` — capa: unit/schemas.
- [x] 1.8 Escribir en rojo y hacer verde `test_patch_estado_desconocido_400` (R5 S8): `EstadoUpdate` acepta el enum completo con `extra="forbid"` y el endpoint traduce valor inválido → 400 por campo — capa: unit/API.
- [x] 1.9 Escribir en rojo y hacer verde `test_ficha_query_desconocida_400` (R6 S7), `test_ficha_cursor_invalido_400` (R6 S8) y `test_ficha_historial_limit_fuera_rango_400` (R6 S3): parseo estricto de `historial_limit` (1–100) y `historial_cursor` con `parse_query_or_400` — capa: API/contrato.
- [x] 1.10 Agregar el `now_provider` inyectable de recepción en `backend/app/modules/turnos/` y escribir en rojo y hacer verde `test_reprogramar_inicio_pasado_400` / `test_reprogramar_inicio_sin_zona_400` (R2 S6) con reloj fijo — capa: unit/servicio.

## 2. Alta staff y reprogramación con anti-solape (DB real)

- [x] 2.1 Parametrizar `reservar()` en `backend/app/modules/turnos/service.py` con `origen`, `actor_id` y `origen_auditoria` (defaults compatibles con C-05) y verificar en verde `test_alta_staff_recepcion_201_origen_recepcion_actor` y `test_alta_staff_sin_sesion_body_publico_sigue_online`; confirmar que no se duplica la transacción — capa: DB real/servicio.
- [x] 2.2 Escribir en rojo y hacer verde `test_reprogramar_mismo_profesional_200_audita_cambios` (R2 S1): `SELECT ... FOR UPDATE` del turno, lock del profesional en el orden de C-05, update de `inicio`/`fin`, conservación de `profesional_id`, `estado` y `token_cancelacion`, auditoría `reprogramar` con `cambios.inicio.antes/despues` — capa: DB real/servicio.
- [x] 2.3 Escribir en rojo y hacer verde `test_reprogramar_cambio_duracion_200` (R2 S2) con `duracion_min` múltiplo de `duracion_default_min` y bloque contiguo libre; y `test_reprogramar_duracion_invalida_400` (R2 S7, parametrizado `0`/`-30`/`40`) — capa: DB real/servicio.
- [x] 2.4 Escribir en rojo y hacer verde `test_reprogramar_slot_ocupado_409_sin_efectos` (R2 S3), `test_reprogramar_slot_no_disponible_409` (R2 S4) y `test_reprogramar_turno_no_editable_422` (R2 S5, parametrizado `cancelado`/`atendido`/`ausente`): 409 con `slot_ocupado`/`slot_no_disponible` + alternativos, sin notificaciones ni auditoría — capa: DB real/API.
- [x] 2.5 Escribir en rojo y hacer verde `test_reprogramar_mismos_valores_noop_200_sin_auditoria` (R2 S8): 200, `notificaciones_encoladas=false`, sin fila de auditoría y sin tocar `updated_at` — capa: DB real/servicio.
- [x] 2.6 Escribir en rojo y hacer verde `test_reprogramar_dos_concurrentes_un_ganador` (R2 S9) con dos transacciones reales al mismo slot: una 200 y otra 409, nunca 500, un solo turno activo en el slot — capa: DB real/concurrencia.

## 3. Cancelación staff normal y forzada (DB real/API)

- [x] 3.1 Escribir en rojo y hacer verde `test_cancelacion_staff_mas_3h_200_audita_cancelar` (R3 S1), `test_cancelacion_staff_exactamente_3h_normal` (R3 S3, borde `>=` con reloj fijo) y `test_cancelacion_staff_mas_3h_con_motivo_audita` (R3 S2): turno `cancelado`, mail `cancelacion` encolado, auditoría `cancelar` con `actor_id` staff y `detalle.motivo` cuando se envía — capa: DB real/API.
- [x] 3.2 Escribir en rojo y hacer verde `test_cancelacion_staff_menos_3h_con_motivo_forzar_200` (R3 S4): 200, `cancelado`, auditoría `forzar_cancelacion` con `detalle.motivo` — capa: DB real/servicio.
- [x] 3.3 Escribir en rojo y hacer verde `test_cancelacion_staff_menos_3h_sin_motivo_422` (R3 S5) y `test_cancelacion_staff_motivo_vacio_o_corto_400` (R3 S6, parametrizado `""`/`"   "`/`"ab"`): sin cambios, sin mail, sin auditoría — capa: DB real/API.
- [x] 3.4 Extender el handler `DELETE /api/turnos/{id}` en `backend/app/modules/turnos/router.py` para despachar por presencia de query (`token` → flujo C-06 con precedencia; sin query → sesión staff `recepcion`/`admin`) y escribir en rojo y hacer verde `test_cancelacion_staff_token_publico_precedencia` (R3 S10) y `test_cancelacion_staff_sin_sesion_401_odontologo_403` (R3 S11) — capa: API/DB real.
- [x] 3.5 Escribir en rojo y hacer verde `test_cancelacion_staff_ya_cancelado_422` (R3 S7) y `test_cancelacion_staff_atendido_ausente_422` (R3 S8): `turno_ya_cancelado` / `turno_no_cancelable`, sin segundo mail ni auditoría — capa: DB real/API.
- [x] 3.6 Escribir en rojo y hacer verde `test_cancelacion_staff_no_borra_fila` (R3 S9) y `test_cancelacion_staff_body_extra_400` (R3 S12): la fila sigue con `estado=cancelado` (duro 3) y `forzar` como clave extra responde 400 por campo — capa: DB real/API.

## 4. Corrección de datos del paciente (DB real)

- [x] 4.1 Escribir en rojo y hacer verde `test_correccion_paciente_telefono_os_200_audita` (R4 S1) en `PUT /api/turnos/{id}/paciente`, actualizando la fila `Paciente` compartida y auditando `editar_paciente` con `cambios.telefono.antes/despues` — capa: DB real/API.
- [x] 4.2 Escribir en rojo y hacer verde `test_correccion_paciente_dni_duplicado_409_sin_fusion` (R4 S3): `dni_duplicado`, ambos pacientes intactos, sin cambio ni auditoría — capa: DB real/servicio.
- [x] 4.3 Escribir en rojo y hacer verde `test_correccion_paciente_mismo_dni_noop_200` (R4 S4), `test_correccion_paciente_campo_vacio_400` (R4 S5), `test_correccion_paciente_dni_formato_invalido_400` (R4 S2) y `test_correccion_paciente_odontologo_403` (R4 S8) — capa: DB real/API.
- [x] 4.4 Escribir en rojo y hacer verde `test_correccion_paciente_visible_en_otros_turnos` (R4 S9) y `test_correccion_paciente_turno_cancelado_permitida` (R4 S10): sin snapshots por turno, corrección habilitada en cualquier estado y auditada — capa: DB real/servicio.

## 5. Transiciones de estado RN-TU-07 (DB real/API)

- [x] 5.1 Escribir en rojo y hacer verde la matriz feliz `test_patch_estado_reservado_confirmado_200` (R5 S1), `test_patch_estado_confirmado_atendido_200` (R5 S2) y `test_patch_estado_confirmado_ausente_200` (R5 S3), cada una con `FOR UPDATE` y auditoría `cambiar_estado` — capa: DB real/API.
- [x] 5.2 Escribir en rojo y hacer verde las inválidas `test_patch_estado_reservado_terminal_422` (R5 S4, parametrizado `atendido`/`ausente`), `test_patch_estado_cancelado_target_422` (R5 S5), `test_patch_estado_reservado_target_422` (R5 S6, parametrizado volver a `reservado` y repetir `confirmado`) y `test_patch_estado_terminal_sin_transiciones_422` (R5 S7) — capa: DB real/API.
- [x] 5.3 Implementar `cambiar_estado()` en `backend/app/modules/turnos/service.py` con la matriz cerrada de D-5 y verificar 5.1–5.2 verdes — capa: DB real/servicio.
- [x] 5.4 Escribir en rojo y hacer verde `test_patch_estado_odontologo_propio_200` (R5 S9), `test_patch_estado_odontologo_ajeno_403` (R5 S10) y `test_patch_estado_odontologo_ausente_403` (R5 S11) usando `require_own_profesional` — capa: API/DB real.
- [x] 5.5 Escribir en rojo y hacer verde `test_patch_estado_dos_concurrentes_una_transicion` (R5 S12): una 200, otra `422 transicion_invalida`, una sola fila de auditoría — capa: DB real/concurrencia.

## 6. Ficha con historial keyset (DB real/API)

- [x] 6.1 Escribir en rojo y hacer verde `test_ficha_recepcion_datos_e_historial_ascendente` (R6 S1): join explícito `Turno→Paciente→Profesional`, columnas nombradas, historial ordenado por `(created_at, id)` — capa: DB real/API.
- [x] 6.2 Escribir en rojo y hacer verde `test_ficha_historial_keyset_sin_offset` (R6 S2): `historial_limit=2` + `next_cursor` base64url, dos páginas sin `OFFSET` — capa: DB real/API.
- [x] 6.3 Escribir en rojo y hacer verde `test_ficha_no_expone_token` (R6 S4), `test_ficha_odontologo_ajeno_403` (R6 S5) y `test_ficha_sin_sesion_401` (R6 S6) — capa: API/DB real.
- [x] 6.4 Escribir en rojo y hacer verde `test_ficha_turno_inexistente_404` (R6 S9) — capa: API.

## 7. RBAC transversal y separación de credenciales (API)

- [x] 7.1 Escribir en rojo y hacer verde `test_staff_endpoints_token_paciente_401` (R7 S2): `GET`/`PUT`/`PATCH` con `?token=` y sin cookie responden 401; y `test_cookie_invalida_401_no_degrada_publico` (R7 S1): una cookie inválida/expirada no reencauza a público — capa: API.
- [x] 7.2 Escribir en rojo y hacer verde `test_recepcion_todas_las_operaciones_staff` (R7 S3), `test_odontologo_escrituras_recepcion_403` (R7 S4) y `test_admin_hereda_operaciones_recepcion` (R7 S5), parametrizando la matriz de D-2 — capa: API/DB real.
- [x] 7.3 Escribir en rojo y hacer verde `test_contratos_publicos_intactos` (R7 S6): reserva sin sesión 201 y cancelación con token 200 siguen igual que C-05/C-06 — capa: API/DB real.

## 8. Notificaciones staff y delta de descarte (DB real/unit)

- [x] 8.1 Escribir en rojo y hacer verde `test_alta_staff_encola_confirmacion_y_recordatorios` (R9 S1): tres pendientes con payload de 11 claves y `enviar_en` ISO-8601 UTC según anticipación — capa: DB real/servicio.
- [x] 8.2 Escribir en rojo y hacer verde `test_cancelacion_staff_encola_cancelacion` (R9 S2) y `test_c07_no_envia_smtp` (R9 S5): una sola `cancelacion` pendiente, `intentos=0`, sin llamada al sender — capa: DB real/API.
- [x] 8.3 Escribir en rojo y hacer verde `test_reprogramacion_descarta_obsoletas_y_encola_nuevas` (R9 S3): pendientes viejas → `fallida` con `error` prefijo `turno_reprogramado:` e `intentos` intactos; nueva `confirmacion` con el `inicio` nuevo; reencolado en savepoint separado — capa: DB real/servicio.
- [x] 8.4 Escribir en rojo y hacer verde `test_reprogramacion_encolado_falla_no_bloquea_200` (R9 S4): mutación y auditoría persisten con `notificaciones_encoladas=false`; si falla el descarte no se intenta el alta nueva — capa: DB real/servicio (mock de borde).
- [x] 8.5 Implementar en `backend/app/modules/notificaciones/payload.py` la clasificación de `turno_reprogramado:` como descarte y escribir en rojo y hacer verde `test_notif_clasifica_turno_reprogramado_como_descarte` (N3 S1) y `test_notif_descarte_no_altera_intentos_ni_toca_enviadas` (N3 S2+S4) — capa: unit/servicio.
- [x] 8.6 Extender el filtro del panel en `backend/app/modules/notificaciones/service.py` (`NOT LIKE 'turno_reprogramado:%'`) y escribir en rojo y hacer verde `test_panel_fallidas_excluye_reprogramadas` (N2 S2) sin cambiar los escenarios existentes de keyset/RBAC/400 — capa: DB real/API.
- [x] 8.7 Escribir en rojo y hacer verde `test_notif_descarte_solo_afecta_su_turno` (N3 S3) y `test_worker_no_reenvia_descartadas` (N1 S3) — capa: DB real/servicio.

## 9. Auditoría append-only (DB real)

- [x] 9.1 Escribir en rojo y hacer verde `test_auditoria_una_fila_por_mutacion_staff` (R8 S1), parametrizando alta/reprogramación/cancelación/forzada/corrección/estado: exactamente una fila con `actor_id` staff, `accion` correcta y `created_at` — capa: DB real/servicio.
- [x] 9.2 Escribir en rojo y hacer verde `test_auditoria_solicitud_rechazada_no_escribe` (R8 S2), parametrizando 400/401/403/409/422 — capa: DB real/API.
- [x] 9.3 Escribir en rojo y hacer verde `test_auditoria_detalle_antes_despues` (R8 S3) y `test_auditoria_actor_y_rol` (R8 S4): `detalle.actor.tipo/id/rol` y `cambios.<campo>.antes/despues` en reprogramación y corrección — capa: DB real/servicio.
- [x] 9.4 Escribir en rojo y hacer verde `test_auditoria_append_only_trigger` (R8 S5): un `UPDATE`/`DELETE` directo sobre la fila falla por `auditoria_no_update_delete` — capa: DB real.

## 10. Integración, regresión y cierre (proceso)

- [x] 10.1 Verificar que no hace falta migración: `Select-String -Path backend/alembic/versions/*.py -Pattern "no_solape_prof|ux_turno_token|notif_tipo|auditoria_no_update_delete"` y `alembic -c backend/alembic.ini current`; documentar que C-07 no toca `backend/alembic/versions/` ni `backend/app/models/` — capa: proceso.
- [x] 10.2 Correr `pytest backend/tests/test_turnos_staff.py backend/tests/test_cancelacion_paciente.py backend/tests/test_notificaciones_worker.py -q` y `ruff check backend`; todo verde — capa: proceso.
- [x] 10.3 Correr la suite completa `pytest backend/tests -q` y confirmar que no hay regresiones en C-01..C-06/C-08, en particular reserva-online, cancelación pública, staff-auth, agenda y panel de fallidas — capa: proceso.
- [x] 10.4 Revisar `git status --short` y `git diff --stat`: solo deben aparecer `backend/app/modules/turnos/{router,service,schemas}.py`, `backend/app/modules/notificaciones/{payload,service}.py`, tests nuevos y `openspec/changes/c-07-crud-recepcion-backend/*`; sin cambios en `backend/app/models/`, `backend/alembic/versions/`, `AGENTS.md`, `CLAUDE.md`, `README.md` ni `.atl/skill-registry.md` — capa: proceso.
- [x] 10.5 Correr `openspec validate c-07-crud-recepcion-backend --strict` y `openspec status --change c-07-crud-recepcion-backend --json`; confirmar artefactos de planificación completos — capa: proceso.
- [x] 10.6 Cerrar el apply log con las decisiones D-1…D-14, el contrato de auditoría uniforme, la interpretación de `ausente` solo para recepción/admin y el punto de coordinación con C-08 (`turno_reprogramado:`) — capa: proceso.

## Trazabilidad escenario → tarea

| Requisito | Escenario | Tarea | Test propuesto | Capa |
|---|---|---|---|---|
| R1 | Alta staff válida crea turno de recepción y responde 201 | 1.3 | `test_alta_staff_recepcion_201_origen_recepcion_actor` | DB real/API |
| R1 | La respuesta staff no expone la credencial del paciente | 1.1 | `test_alta_staff_respuesta_sin_token` | unit/schemas |
| R1 | Sin sesión, `origen` en el body público sigue siendo 400 por campo | 1.2 | `test_alta_staff_sin_sesion_origen_400_no_regresion` | API/contrato |
| R1 | Sin sesión y body público válido sigue creando origen online | 1.2 | `test_alta_staff_sin_sesion_body_publico_sigue_online` | API/contrato |
| R1 | Odontólogo no puede crear turnos | 1.3 | `test_alta_staff_odontologo_403` | API/DB real |
| R1 | Body staff incompleto responde 400 por campo | 1.1 | `test_alta_staff_body_incompleto_400_por_campo` | unit/schemas |
| R1 | Slot ocupado responde 409 con alternativos y sin paciente nuevo | 1.4 | `test_alta_staff_slot_ocupado_409_alternativos_sin_paciente` | DB real/API |
| R1 | Profesional inexistente o inactivo responde 404 | 1.4 | `test_alta_staff_profesional_inexistente_o_inactivo_404` | DB real/API |
| R1 | Fallo del encolado no bloquea el alta staff | 1.5 | `test_alta_staff_encolado_falla_201_notificaciones_false` | DB real/servicio |
| R1 | `origen` ausente o distinto de recepcion responde 400 | 1.1 | `test_alta_staff_origen_ausente_o_invalido_400` | unit/schemas |
| R2 | Reprogramación válida mueve el turno y audita antes→después | 2.2 | `test_reprogramar_mismo_profesional_200_audita_cambios` | DB real/servicio |
| R2 | Cambio de duración recalcula fin y respeta la granularidad | 2.3 | `test_reprogramar_cambio_duracion_200` | DB real/servicio |
| R2 | Destino ocupado responde 409 con alternativos y sin efectos | 2.4 | `test_reprogramar_slot_ocupado_409_sin_efectos` | DB real/API |
| R2 | Destino fuera de ventana o no contiguo responde 409 slot_no_disponible | 2.4 | `test_reprogramar_slot_no_disponible_409` | DB real/API |
| R2 | Turno cancelado, atendido o ausente no es editable | 2.4 | `test_reprogramar_turno_no_editable_422` | DB real/API |
| R2 | `inicio` pasado o sin zona responde 400 | 1.10 | `test_reprogramar_inicio_pasado_400` / `test_reprogramar_inicio_sin_zona_400` | unit/servicio |
| R2 | `duracion_min` inválida responde 400 | 2.3 | `test_reprogramar_duracion_invalida_400` | DB real/servicio |
| R2 | Reprogramar a los mismos valores es un 200 no-op | 2.5 | `test_reprogramar_mismos_valores_noop_200_sin_auditoria` | DB real/servicio |
| R2 | Dos reprogramaciones concurrentes al mismo slot tienen un solo ganador | 2.6 | `test_reprogramar_dos_concurrentes_un_ganador` | DB real/concurrencia |
| R2 | Campo extra en el body responde 400 por campo | 1.6 | `test_reprogramar_campo_extra_400` | unit/schemas |
| R3 | Cancelación staff con 3 h o más audita `cancelar` | 3.1 | `test_cancelacion_staff_mas_3h_200_audita_cancelar` | DB real/API |
| R3 | Un motivo enviado en la rama normal se guarda en la auditoría | 3.1 | `test_cancelacion_staff_mas_3h_con_motivo_audita` | DB real/API |
| R3 | Exactamente 3 horas se trata como cancelación normal | 3.1 | `test_cancelacion_staff_exactamente_3h_normal` | DB real/API |
| R3 | Cancelación forzada con menos de 3 h y motivo audita `forzar_cancelacion` | 3.2 | `test_cancelacion_staff_menos_3h_con_motivo_forzar_200` | DB real/servicio |
| R3 | Forzar sin motivo responde 422 y no cambia nada | 3.3 | `test_cancelacion_staff_menos_3h_sin_motivo_422` | DB real/API |
| R3 | Motivo vacío o demasiado corto responde 400 | 3.3 | `test_cancelacion_staff_motivo_vacio_o_corto_400` | DB real/API |
| R3 | Turno ya cancelado responde 422 sin efectos laterales | 3.5 | `test_cancelacion_staff_ya_cancelado_422` | DB real/API |
| R3 | Turno atendido o ausente responde 422 | 3.5 | `test_cancelacion_staff_atendido_ausente_422` | DB real/API |
| R3 | La cancelación staff no elimina la fila del turno | 3.6 | `test_cancelacion_staff_no_borra_fila` | DB real/API |
| R3 | El token público sigue funcionando y tiene precedencia | 3.4 | `test_cancelacion_staff_token_publico_precedencia` | API/DB real |
| R3 | Odontólogo y cliente sin sesión no cancelan como staff | 3.4 | `test_cancelacion_staff_sin_sesion_401_odontologo_403` | API/DB real |
| R3 | Campo extra en el body staff responde 400 | 3.6 | `test_cancelacion_staff_body_extra_400` | DB real/API |
| R4 | Corrección de teléfono y obra social audita antes→después | 4.1 | `test_correccion_paciente_telefono_os_200_audita` | DB real/API |
| R4 | DNI con formato inválido responde 400 | 4.3 | `test_correccion_paciente_dni_formato_invalido_400` | DB real/API |
| R4 | DNI ya usado por otro paciente responde 409 sin fusionar | 4.2 | `test_correccion_paciente_dni_duplicado_409_sin_fusion` | DB real/servicio |
| R4 | Corregir al mismo DNI actual es un 200 no-op | 4.3 | `test_correccion_paciente_mismo_dni_noop_200` | DB real/API |
| R4 | Campo vacío o solo espacios responde 400 | 4.3 | `test_correccion_paciente_campo_vacio_400` | DB real/API |
| R4 | Body sin campos responde 400 | 1.7 | `test_correccion_paciente_body_sin_campos_400` | unit/schemas |
| R4 | `nombre` o `email` fuera del contrato responde 400 | 1.7 | `test_correccion_paciente_nombre_email_400` | unit/schemas |
| R4 | Odontólogo no corrige datos del paciente | 4.3 | `test_correccion_paciente_odontologo_403` | DB real/API |
| R4 | La corrección se refleja en los demás turnos del mismo paciente | 4.4 | `test_correccion_paciente_visible_en_otros_turnos` | DB real/servicio |
| R4 | Se permite corregir datos de un turno cancelado | 4.4 | `test_correccion_paciente_turno_cancelado_permitida` | DB real/servicio |
| R5 | reservado a confirmado responde 200 y audita | 5.1 | `test_patch_estado_reservado_confirmado_200` | DB real/API |
| R5 | confirmado a atendido responde 200 | 5.1 | `test_patch_estado_confirmado_atendido_200` | DB real/API |
| R5 | confirmado a ausente responde 200 | 5.1 | `test_patch_estado_confirmado_ausente_200` | DB real/API |
| R5 | reservado a atendido o ausente responde 422 | 5.2 | `test_patch_estado_reservado_terminal_422` | DB real/API |
| R5 | Cancelar por PATCH estado responde 422 | 5.2 | `test_patch_estado_cancelado_target_422` | DB real/API |
| R5 | Volver a reservado o repetir confirmado responde 422 | 5.2 | `test_patch_estado_reservado_target_422` | DB real/API |
| R5 | Estados terminales no admiten transiciones | 5.2 | `test_patch_estado_terminal_sin_transiciones_422` | DB real/API |
| R5 | Estado desconocido responde 400 | 1.8 | `test_patch_estado_desconocido_400` | unit/API |
| R5 | Odontólogo marca estado de sus propios turnos | 5.4 | `test_patch_estado_odontologo_propio_200` | API/DB real |
| R5 | Odontólogo no marca estado de turnos ajenos | 5.4 | `test_patch_estado_odontologo_ajeno_403` | API/DB real |
| R5 | Odontólogo no marca ausente | 5.4 | `test_patch_estado_odontologo_ausente_403` | API/DB real |
| R5 | Dos PATCH concurrentes producen una sola transición | 5.5 | `test_patch_estado_dos_concurrentes_una_transicion` | DB real/concurrencia |
| R6 | Ficha muestra datos e historial ascendente | 6.1 | `test_ficha_recepcion_datos_e_historial_ascendente` | DB real/API |
| R6 | Historial usa keyset sin OFFSET | 6.2 | `test_ficha_historial_keyset_sin_offset` | DB real/API |
| R6 | Historial con límite fuera de rango responde 400 | 1.9 | `test_ficha_historial_limit_fuera_rango_400` | API/contrato |
| R6 | La ficha no expone el token de cancelación | 6.3 | `test_ficha_no_expone_token` | DB real/API |
| R6 | Odontólogo no ve la ficha de un turno ajeno | 6.3 | `test_ficha_odontologo_ajeno_403` | API/DB real |
| R6 | Ficha sin sesión responde 401 | 6.3 | `test_ficha_sin_sesion_401` | API/DB real |
| R6 | Query desconocida responde 400 por campo | 1.9 | `test_ficha_query_desconocida_400` | API/contrato |
| R6 | Cursor de historial inválido responde 400 | 1.9 | `test_ficha_cursor_invalido_400` | API/contrato |
| R6 | Turno inexistente responde 404 | 6.4 | `test_ficha_turno_inexistente_404` | API |
| R7 | Cookie inválida o expirada responde 401 y no degrada a público | 7.1 | `test_cookie_invalida_401_no_degrada_publico` | API |
| R7 | Token de paciente no autentica rutas staff | 7.1 | `test_staff_endpoints_token_paciente_401` | API |
| R7 | Recepción accede a todas las operaciones staff | 7.2 | `test_recepcion_todas_las_operaciones_staff` | API/DB real |
| R7 | Odontólogo no accede a escrituras de recepción | 7.2 | `test_odontologo_escrituras_recepcion_403` | API/DB real |
| R7 | Admin hereda las operaciones de recepción | 7.2 | `test_admin_hereda_operaciones_recepcion` | API/DB real |
| R7 | Los contratos públicos no cambian | 7.3 | `test_contratos_publicos_intactos` | API/DB real |
| R8 | Cada mutación staff escribe una fila de auditoría | 9.1 | `test_auditoria_una_fila_por_mutacion_staff` | DB real/servicio |
| R8 | Una solicitud rechazada no escribe auditoría | 9.2 | `test_auditoria_solicitud_rechazada_no_escribe` | DB real/API |
| R8 | Reprogramación y corrección guardan antes y después | 9.3 | `test_auditoria_detalle_antes_despues` | DB real/servicio |
| R8 | La auditoría identifica actor y rol | 9.3 | `test_auditoria_actor_y_rol` | DB real/servicio |
| R8 | La auditoría sigue siendo append-only | 9.4 | `test_auditoria_append_only_trigger` | DB real |
| R9 | Alta staff encola confirmación y recordatorios según anticipación | 8.1 | `test_alta_staff_encola_confirmacion_y_recordatorios` | DB real/servicio |
| R9 | Cancelación staff encola el mail cancelacion | 8.2 | `test_cancelacion_staff_encola_cancelacion` | DB real/API |
| R9 | Reprogramación descarta lo obsoleto y encola lo nuevo | 8.3 | `test_reprogramacion_descarta_obsoletas_y_encola_nuevas` | DB real/servicio |
| R9 | Fallo del encolado no bloquea la mutación staff | 8.4 | `test_reprogramacion_encolado_falla_no_bloquea_200` | DB real/servicio |
| R9 | C-07 no envía SMTP en la request | 8.2 | `test_c07_no_envia_smtp` | DB real/API |
| N1 | Turno cancelado no recibe recordatorio | (existente) | `test_notif_turno_cancelado_no_envia` | DB real/servicio |
| N1 | Turno atendido no recibe recordatorio vencido | (existente) | `test_notif_turno_atendido_no_envia` | DB real/servicio |
| N1 | Notificación ya descartada por reprogramación no se reenvía | 8.7 | `test_worker_no_reenvia_descartadas` | DB real/servicio |
| N2 | Recepción lista fallidas con paginación keyset | (existente) | `test_panel_fallidas_keyset` | DB real/API |
| N2 | Las fallidas por reprogramación no aparecen en el panel | 8.6 | `test_panel_fallidas_excluye_reprogramadas` | DB real/API |
| N2 | Odontólogo no accede al panel de fallidas | (existente) | `test_panel_fallidas_odontologo_403` | API |
| N2 | Sin sesión responde 401 | (existente) | `test_panel_fallidas_sin_sesion_401` | API |
| N2 | Parámetro desconocido responde 400 por campo | (existente) | `test_panel_fallidas_query_extra_400` | API |
| N2 | Cursor inválido responde 400 por campo | (existente) | `test_panel_fallidas_cursor_invalido_400` | API |
| N3 | El prefijo turno_reprogramado se clasifica como descarte | 8.5 | `test_notif_clasifica_turno_reprogramado_como_descarte` | unit/servicio |
| N3 | Descartar pendientes no altera intentos ni invoca SMTP | 8.3 | `test_reprogramacion_descarta_obsoletas_y_encola_nuevas` | DB real/servicio |
| N3 | El descarte no afecta notificaciones de otros turnos | 8.7 | `test_notif_descarte_solo_afecta_su_turno` | DB real/servicio |
| N3 | Una notificación enviada nunca se marca fallida por reprogramación | 8.5 | `test_notif_descarte_no_altera_intentos_ni_toca_enviadas` | unit/servicio |

## Workflow follow-up

- Ejecutar `/opsx:apply c-07-crud-recepcion-backend` recién con una orden nueva; este propose no implementa código.
- Después de la revisión con `turno-spec-review` y de que la suite esté verde, ejecutar `/opsx:archive c-07-crud-recepcion-backend` y marcar C-07 como completado en `CHANGES.md` (fuera de este paso).
- No commitear ni pushear hasta que el usuario lo pida explícitamente.

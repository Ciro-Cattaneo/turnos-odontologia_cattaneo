# Apply log — c-06-cancelacion-paciente-backend

Fecha: 2026-11-07. **Lotes:** §1 (contrato/schemas/config + parseo de query),
§2 (servicio, lock, regla temporal, soft cancel), §3 (router y errores HTTP),
§4 (encolado del mail `cancelacion`), §5 (auditoría append-only) y §6 (rate
limit del endpoint público). Suite: **400 baseline → 438** (+38 tests nuevos),
sin regresiones. `python -m ruff check backend` limpio. Sin migración (§1.1).
**Change completo: 39/39 tareas.**

## Evidencia de cierre (§7)

- **7.1:** `Select-String` sobre `backend/alembic/versions/001_core_models.py`
  confirma `ux_turno_token` (188), `notif_tipo` con `cancelacion` (297-298) y
  `no_solape_prof` (40); `python -m alembic -c backend/alembic.ini current` →
  `002_agenda_meta (head)`. C-06 **no toca** `backend/app/models/` ni
  `backend/alembic/versions/`.
- **7.2:** `python -m pytest backend/tests/test_cancelacion_paciente.py -q` →
  **38 passed**; `python -m ruff check backend` → **All checks passed!**
- **7.3:** `python -m pytest backend/tests -q` → **438 passed** (26 warnings
  preexistentes de SQLAlchemy/Starlette), sin fallos C-02/C-03/C-04/C-05.
- **7.4:** `git status --short` acotado a `.env.example`,
  `backend/app/core/config.py`, `backend/app/modules/turnos/{router,schemas}.py`,
  `backend/app/modules/turnos/cancellation_service.py`,
  `backend/tests/test_cancelacion_paciente.py` y
  `openspec/changes/c-06-cancelacion-paciente-backend/`. Nada de `main.py`,
  `models/`, `alembic/`, `AGENTS.md`, `CLAUDE.md`, `CHANGES.md` ni
  `.atl/skill-registry.md`; los `.pyc` son artefactos de build.
- **7.5:** `openspec validate c-06-cancelacion-paciente-backend --strict` →
  **Change 'c-06-cancelacion-paciente-backend' is valid**;
  `openspec status --change ... --json` → `isPlanningComplete: true`,
  `isComplete: true`.
- **7.6:** este archivo.

## 1.1 Verificación de migración (precondición de D-12)

- `token_cancelacion` ya existe en `001_core_models.py` con
  `UniqueConstraint(..., name="ux_turno_token")`; el enum `notif_tipo` ya
  incluye `cancelacion`.
- `alembic current` → `002_agenda_meta (head)` (sin cambios).
- Conclusión: D-12 se sostiene; no hay `upgrade`/`downgrade` ni cambios de
  schema en este change.

## Decisiones implementadas

### D-1. Router delgado + `cancellation_service` + schemas estrictos

- `backend/app/modules/turnos/cancellation_service.py` (nuevo): excepciones de
  dominio (`NoAutorizado`, `TurnoYaCancelado`, `TurnoNoCancelable`,
  `FueraDePlazo`, `DatoInvalido`), helpers `_utc`, `_payload`, `_encolar` y
  `cancelar(db, *, turno_id, token, now_provider=None)` que devuelve el dict de
  respuesta (tipado estricto, sin `Any`).
- `backend/app/modules/turnos/router.py`: la ruta solo parsea query, inyecta el
  reloj por `now_utc` y traduce errores; no contiene lógica de persistencia.
- `backend/app/modules/turnos/schemas.py`: `CancelacionOut` con
  `ConfigDict(extra="forbid")` y siete campos declarados.

### D-2. Token de query y `403` genérico uniforme

- Filtro `Turno.id == turno_id, Turno.token_cancelacion == token`; ausencia de
  fila ⇒ `403 {"detail": "No autorizado"}`.
- Query manual (`_parse_query_token`): exactamente una clave `token`; claves
  extra (`dni`, `telefono`, …) o `token` repetido ⇒ `400` antes de mirar la
  credencial.
- `token` en body/header no autentica (`403`); `id` malformado también `403`
  (`_parse_uuid`), sin distinguir "no existe" de "no autorizado".

### D-3. Regla temporal con borde inclusivo

- `inicio - now < timedelta(hours=CANCEL_HOURS_MIN)` ⇒ rechazo; exactamente 3 h
  se acepta (`test_..._exactamente_3h_acepta_200`). Umbral leído de
  `Settings.CANCEL_HOURS_MIN` (default 3), cubierto con 5 h vía
  `get_settings.cache_clear()` + `monkeypatch`.

### D-4. Transacción, lock y concurrencia

- `SELECT ... FOR UPDATE` por `id`+`token` con `load_only` de columnas
  explícitas (regla dura 7); sin `SELECT *`.
- `test_cancelacion_dos_concurrentes_un_solo_efecto` usa dos `Session` reales
  sobre `test_engine` (commits reales): la segunda espera el lock y recibe
  `422 turno_ya_cancelado`, no `500`.

### D-5. Idempotencia relativa

- Segundo intento sobre un turno `cancelado` ⇒ `422 detail=codigo
  turno_ya_cancelado`, sin nueva notificación ni auditoría
  (`test_..._cancelado_422_sin_efectos`).

### D-6. Contrato de encolado del mail `cancelacion` (tarea 4.4)

- Se inserta **exactamente una** fila `Notificacion` con `canal=mail`,
  `tipo=cancelacion`, `estado=pendiente`, `intentos=0`, `enviada_at=NULL`.
- Payload con las **11 claves** de `app/modules/notificaciones/payload.py`
  (`REQUIRED_KEYS`, sin agregados): `turno_id`, `tipo`, `enviar_en`,
  `paciente_nombre`, `paciente_email`, `profesional_nombre`, `inicio`, `fin`,
  `duracion_min`, `token_cancelacion`, `cancel_url`. Timestamps ISO-8601 UTC y
  `enviar_en = now` de la cancelación.
- Sin `dni`, `telefono` ni `obra_social` en el payload (minimización, regla
  dura 12).
- El insert corre dentro de `db.begin_nested()`: cualquier excepción se atrapa,
  se loguea un warning y la cancelación sigue con
  `notificaciones_encoladas=false` (regla dura 5). C-06 **solo encola**: no
  importa ni invoca el sender SMTP; la fila queda `pendiente` para C-08.

### D-7. Auditoría append-only con actor paciente

- `AuditoriaTurno(accion="cancelar", actor_id=None, detalle={...})` con
  `actor="paciente"`, `credencial="token_cancelacion"`, `estado_previo`,
  `inicio`/`fin` ISO UTC, `duracion_min`, `profesional_id` y
  `notificaciones_encoladas`.
- El token no se persiste ni se loguea: `test_..._auditoria_no_guarda_token`
  revisa `detalle` y los registros de loggers `app.*`.
- Ninguna solicitud rechazada (400/403/422) escribe auditoría
  (`test_..._400_422_no_escriben_auditoria`, parametrizado).

### D-8. Rate limit coherente con C-05

- Dependencia `public_cancelacion_throttle` con clave
  `turnos-cancelacion:{ip}` (10/min, ventana fija 60 s) reutilizando
  `check_public_rate_limit` y `get_client_ip`.
- Va en `dependencies=[...]` de la operación ⇒ `429` + `Retry-After` se emite
  antes de evaluar query o credencial (el intento 11 con token inválido
  devuelve `429`, no `403`).

### D-9. Soft cancel

- `turno.estado = cancelado` + `updated_at = now`; la fila nunca se borra
  (`test_..._no_elimina_fila_turno`).

### D-10. TZ/UTC y token sin expiración independiente

- `now` siempre aware y normalizado a UTC; `_utc` rechaza datetimes naive y el
  router lo traduce a `500` genérico (`DatoInvalido`).
- No se agregó expiración propia del token: vence por la regla de 3 h.

### D-11. Contrato HTTP y contacto del consultorio

- `DELETE /api/turnos/{id}?token=` → `200 CancelacionOut`
  (`id`, `estado`, `inicio`, `fin`, `duracion_min`,
  `notificaciones_encoladas`, `mensaje`).
- `403` genérico; `422` con códigos `cancelacion_fuera_de_plazo` (incluye
  `mensaje` y `contacto`), `turno_ya_cancelado` y `turno_no_cancelable`;
  `429` con `Retry-After`; `400` por query inválida.
- `CONSULTORIO_CONTACTO` en `backend/app/core/config.py` y `.env.example`,
  default "Comunicate con el consultorio para coordinar la cancelación".

### D-12. Sin migración

- Ver §1.1.

### D-13. Respuesta y pruebas sin datos reales

- Todos los tests usan pacientes/DNI/teléfonos ficticios y emails `.test`.

## Interpretación de "token expirado" (cierre 7.6)

No existe vencimiento propio del token (D-10): un token es válido mientras el
turno exista y su `inicio` esté dentro de la ventana. Por eso:

- **Token inexistente o de otro turno** → `403` genérico (no revela si el turno
  existe).
- **Token válido pero turno ya pasado / dentro de las 3 h** → `422
  cancelacion_fuera_de_plazo` con `mensaje` + `contacto`.
- **Token válido pero turno ya cancelado** → `422 turno_ya_cancelado`.
- **Token válido pero estado `atendido`/`ausente`** → `422
  turno_no_cancelable`.

`CONSULTORIO_CONTACTO` (default "Comunicate con el consultorio para coordinar
la cancelación") se devuelve **solo** en el `422` de plazo, para dar al
paciente un canal alternativo cuando ya no puede cancelar online; es
configurable por env y no forma parte del payload de notificación.

## Evidencia TDD

| Tarea | Test | Capa | RED | GREEN | TRIANGULATE / mutación |
|---|---|---|---|---|---|
| 1.1 | `test_cancelacion_out_extra_forbid`, `test_cancelacion_respuesta_solo_campos_declarados` | unit/schema | `ImportError CancelacionOut` | 2 passed | `extra="allow"` mata (extra prohibido) |
| 1.2 | `test_cancelacion_contacto_default_y_env` | unit/config | `AttributeError CONSULTORIO_CONTACTO` | 1 passed | default y override por env |
| 1.3 | `test_cancelacion_query_token_repetido_400`, `..._query_dni_telefono_400` | API | `404` (ruta inexistente) | 3 passed | parseo manual vs `token: str = Query()` |
| 1.4 | `test_cancelacion_inicio_iso_utc_en_respuesta` | API | `404` | 1 passed | offset UTC obligatorio |
| 2.1–2.2 | `..._mas_de_3h_cancela_y_libera_slot`, `..._turno_confirmado_cancela_200` | DB/servicio | `ImportError cancellation_service` | 2 passed | soft cancel + slip de slot |
| 2.3 | `..._exactamente_3h_acepta_200` | servicio | 422 indebido | 1 passed | mutación `<`→`<=` ⇒ **mata** |
| 2.4–2.6 | `..._menos_de_3h_422_con_contacto`, `..._ventana_expirada_422_no_403`, `..._umbral_configurable_5h_422` | API | 404/200 indebido | 3 passed | umbral configurable |
| 2.7 | `..._no_elimina_fila_turno` | DB | — | 1 passed | DELETE físico mata |
| 2.8 | `..._dos_concurrentes_un_solo_efecto` | DB/concurrencia real | sin `FOR UPDATE` ⇒ doble efecto | 1 passed | lock obligatorio |
| 2.9 | `..._cancelado_422_sin_efectos` | API/DB | 200 repetido | 1 passed | mutación quitar guarda de estado ⇒ **mata** |
| 3.1–3.8 | token inválido/ausente/malformado/de otro turno/id inexistente/id malformado/token en body/403 no revela | API | 404 | 8 passed | filtro por `id`+`token` |
| 3.7 | `..._atendido_o_ausente_422` (parametrizado) | API | 200 indebido | 2 passed | `ESTADOS_CANCELABLES` |
| 3.9 | `..._dos_concurrentes_un_solo_efecto` | DB real | 500 por `IntegrityError` | 1 passed | traducción de excepción |
| 4.1 | `..._encola_mail_cancelacion_pendiente` | DB/servicio | sin fila | 1 passed | 11 claves exactas |
| 4.2 | `..._encolado_falla_no_bloquea_200` | DB (mock de borde) | 500 | 1 passed | fallback `false` |
| 4.3 | `..._no_envia_smtp_ni_crea_otra_cola` | API/DB | — | 1 passed | sender parcheado a `raise` |
| 4.4 | — | documentación | N/A | apply log (D-6) | contrato leído de `payload.REQUIRED_KEYS` |
| 5.1 | `..._escribe_auditoria_actor_paciente` | DB/servicio | sin auditoría | 1 passed | detalle completo |
| 5.2 | `..._400_422_no_escriben_auditoria` (parametrizado 3 casos) | API/DB | filas espurias | 3 passed | rechazo sin efectos |
| 5.3 | `..._auditoria_no_guarda_token` | servicio/logs | token filtrado | 1 passed | revisa `detalle` y loggers `app.*` |
| 6.1 | `..._rate_limit_dentro_limite_200` | API/dependencia | 429 prematuro o cupo no consumido | 1 passed | mutación quitar throttle ⇒ **mata** |
| 6.2 | `..._rate_limit_exceso_429_sin_cancelar` | API/dependencia | 200 con cupo agotado | 1 passed | idem |
| 6.3 | `..._rate_limit_decimo_pasa_undecimo_429` | API/dependencia | 11.º = 403 | 1 passed | idem (precedencia 429 > 403) |
| 6.4 | dependencia `public_cancelacion_throttle` | API/dependencia | N/A | 3 passed | clave por IP |

Mutaciones dirigidas ejecutadas y restauradas: `<`→`<=` en la regla temporal
(mata 2.3), remoción de la guarda de estado `cancelado` (mata 2.9) y remoción
de `dependencies=[...]` del throttle (mata 6.1–6.3). Tras restaurar,
`38 passed`.

## Decisiones no obvias / desviaciones

1. **`caplog` acotado a loggers `app.*`** en 5.3: el `TestClient` de httpx
   registra la URL completa (`?token=…`) en su access log, que no es logging de
   la aplicación. El test valida que el token no aparece en `detalle` ni en los
   registros emitidos por `app.*`; documentar que un access log de proxy sí
   vería el token en la query (inevitable con credencial en URL, propio de
   C-05/D-2).
2. **Limpieza de datos commiteados en tests:** el trigger append-only
   `auditoria_no_update_delete` bloquea el DELETE de setup; los helpers
   `_setup_commit`/`_limpiar_commit` desactivan el trigger solo para limpiar
   filas de prueba y lo rehabilitan.
3. **`db_session` con savepoints:** no sirve para concurrencia real porque el
   rollback externo descarta todo; 2.8/3.9 abren `Session(bind=test_engine)`
   con commits reales.
4. **EXCLUDE `no_solape_prof`:** los turnos de prueba del mismo profesional no
   pueden solaparse; el turno de "otro turno" se ubica con offset para evitar
   violar la constraint (corregido durante §3).
5. **`_parse_uuid` devuelve `None`** y el router responde `403` genérico en vez
   de `422`, para no distinguir formato inválido de credencial inválida.
6. **`duracion_min` sale del turno persistido** (no se recalcula) en respuesta,
   payload y auditoría.

## Puntos abiertos / coordinación

- **C-08 (worker):** consume la fila `Notificacion cancelacion` ya encolada con
  `enviar_en=now`; C-06 no envía SMTP. Si C-08 requiere columnas propias, las
  agrega con su migración (no en C-06).
- **`CONSULTORIO_CONTACTO`:** texto provisorio v1; reemplazable por env sin
  cambio de contrato.
- Sin otros pendientes: **change completo (39/39)**; próximo paso
  `/opsx:archive c-06-cancelacion-paciente-backend` bajo orden explícita.

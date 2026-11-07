# Tasks — c-08-notificaciones-mail-worker

> TDD: cada tarea de código arranca con el test en rojo, luego el mínimo para verde y refactor. Mocks solo en el borde SMTP y en el reloj; la persistencia usa Postgres real (`db_session`). Nombres `test_<escenario>_<resultado>`.

## 1. Dependencias y configuración

- [x] 1.1 Agregar `apscheduler>=3.10,<4` a `backend/requirements.txt` e instalar; verificar con `python -c "import apscheduler; print(apscheduler.__version__)"` (capa: dependencias)
- [x] 1.2 Agregar `SMTP_TIMEOUT_S=15`, `NOTIF_WORKER_ENABLED=True`, `NOTIF_WORKER_INTERVAL_MIN=5` y `NOTIF_WORKER_BATCH_SIZE=20` a `Settings`, con validación 5–10 para el intervalo y error claro al boot; extender `backend/tests/test_config.py` con `test_config_worker_defaults_aplican` y `test_config_intervalo_fuera_de_rango_falla` (capa: unit/config; verificación: `pytest backend/tests/test_config.py -q`)
- [x] 1.3 Documentar las nuevas vars en `.env.example` con valores ficticios y comentario de que `REDIS_URL` sigue sin uso; verificar `pytest backend/tests/test_env_example.py -q` (capa: contrato/static)
- [x] 1.4 Fijar `NOTIF_WORKER_ENABLED=false` en `backend/tests/conftest.py` (sin tocar las 13 vars requeridas) y verificar que `app.main` importa y `pytest backend/tests/test_health.py -q` pasa (capa: test harness)

## 2. Contrato de payload y motivos de error

- [x] 2.1 Implementar `validar_payload(payload) -> PayloadValido` y `parsear_enviar_en(payload) -> datetime` en `backend/app/modules/notificaciones/payload.py` con las 11 claves de D-1; tests `test_payload_completo_devuelve_datos`, `test_payload_sin_campo_devuelve_incompleto` y `test_payload_enviar_en_invalido_no_parsea` (capa: unit)
- [x] 2.2 Definir los prefijos de `error` (`smtp:`, `payload_incompleto:`, `turno_cancelado:`) y helpers de clasificación en `payload.py`; test `test_motivo_turno_cancelado_se_clasifica_descarte` y `test_motivo_smtp_se_clasifica_fallo` (capa: unit)

## 3. Plantillas de mail

- [x] 3.1 Implementar `render(tipo, payload) -> (asunto, cuerpo)` para `confirmacion`, `recordatorio_24h` y `recordatorio_2h` en `backend/app/modules/notificaciones/templates.py`; tests `test_plantilla_confirmacion_incluye_hora_local_y_link`, `test_plantilla_recordatorio_incluye_profesional_y_link` y `test_plantilla_no_incluye_dni_telefono_ni_obra_social` (capa: unit; usar payload ficticio `.test`)
- [x] 3.2 Implementar la plantilla `cancelacion` (sin link de cancelación); test `test_plantilla_cancelacion_no_incluye_link_de_cancelacion` (capa: unit)

## 4. Cliente SMTP inyectable

- [x] 4.1 Implementar `SMTPSender` con stdlib (`SMTP` + `starttls` en 587, `SMTP_SSL` en 465, `EmailMessage`, `timeout=SMTP_TIMEOUT_S`); tests con `monkeypatch` de `smtplib.SMTP`/`SMTP_SSL` en el borde: `test_sender_587_usa_starttls_y_login` y `test_sender_465_usa_ssl_y_respeta_timeout` (capa: integración de borde)
- [x] 4.2 Envolver errores de conexión/login/envío en `SendError` con mensaje acotado (sin `SMTP_PASS`); test `test_sender_error_de_login_se_envuelve_sin_password` (capa: unit/borde)
- [x] 4.3 Definir el protocolo `MailSender` y la fábrica por defecto; inyectarlo en el worker y verificar `test_worker_usa_sender_inyectado` (capa: unit)

## 5. Worker `run_once`

- [x] 5.1 Implementar la selección/claim de una pendiente vencida con `JOIN turno`, columnas explícitas, `pg_input_is_valid`, `FOR UPDATE OF n SKIP LOCKED` y `LIMIT 1`; tests `test_worker_toma_pendiente_vencida` y `test_worker_no_toma_notificacion_futura` (capa: DB real)
- [x] 5.2 Camino feliz: enviar y marcar `enviada` + `enviada_at`, `error=NULL`, sin cambiar el turno; tests `test_worker_confirmacion_vencida_queda_enviada` y `test_worker_no_modifica_estado_del_turno` (capa: DB real + sender fake)
- [x] 5.3 Fallo SMTP: `intentos++`, `error` persistido y backoff exacto (`+5 min` tras el 1.º, `+10 min` tras el 2.º); tests `test_worker_primer_fallo_reprograma_cinco_minutos` y `test_worker_segundo_fallo_reprograma_diez_minutos` (capa: DB real + sender fake que falla)
- [x] 5.4 Tercer fallo → `fallida` con `intentos=3` y sin nueva programación; test `test_worker_tercer_fallo_queda_fallida` (capa: DB real)
- [x] 5.5 Reintento exitoso con `intentos=1` → `enviada` y `error NULL`; test `test_worker_reintento_exitoso_queda_enviada` (capa: DB real)
- [x] 5.6 Descarte por turno no activo (`cancelado`, `atendido`, `ausente`): `fallida` + `turno_cancelado`, `intentos` sin cambios y sin llamada SMTP; tests `test_worker_turno_cancelado_no_envia_recordatorio` y `test_worker_turno_atendido_descarta_recordatorio` (capa: DB real + sender fake que registra llamadas)
- [x] 5.7 `cancelacion` se envía aunque el turno esté `cancelado`; test `test_worker_cancelacion_se_envia_con_turno_cancelado` (capa: DB real)
- [x] 5.8 Saneamiento de payload incompleto (`enviar_en` ausente o inválido): `fallida` + `payload_incompleto`, sin SMTP y sin romper el lote; tests `test_worker_payload_sin_email_se_marca_fallida_sin_romper_lote` y `test_worker_enviar_en_invalido_se_marca_fallida` (capa: DB real + sender fake)
- [x] 5.9 Aislamiento de excepciones por fila y resumen de contadores (`enviadas`, `reintentos`, `fallidas`, `descartadas`, `payload_invalidos`); tests `test_worker_excepcion_inesperada_no_aborta_lote` y `test_worker_resumen_cuenta_resultados` (capa: unit/DB)
- [x] 5.10 Logs estructurados por resultado sin `SMTP_PASS` ni datos sensibles; test `test_worker_log_de_fallo_no_incluye_password` con `caplog` (capa: unit)

## 6. Scheduler y lifespan

- [x] 6.1 Implementar `crear_scheduler()` con `BackgroundScheduler`, `add_job(..., trigger="interval", minutes=NOTIF_WORKER_INTERVAL_MIN, id="notificaciones-mail", max_instances=1, coalesce=True)` y jobstore en memoria; test `test_scheduler_registra_job_con_intervalo_configurado` (capa: unit)
- [x] 6.2 Integrar el scheduler en el `lifespan` de `app/main.py` (start/stop con `shutdown(wait=False)`) respetando `NOTIF_WORKER_ENABLED`; tests `test_lifespan_arranca_scheduler_con_flag_true` y `test_lifespan_no_arranca_scheduler_con_flag_false` (capa: API/lifespan; usar monkeypatch del scheduler, sin red)
- [x] 6.3 Evitar solapamiento con un lock de módulo no bloqueante: segundo ciclo se omite y se loguea; test `test_worker_ciclo_solapado_se_omite` (capa: unit)
- [x] 6.4 Verificar que `REDIS_URL` no se usa en ningún camino del worker; test `test_worker_no_requiere_redis` (capa: static/unit)

## 7. Endpoint de fallidas

- [x] 7.1 Implementar `FallidasQuery` (`extra="forbid"`, `limit` 1–200 default 50) y el codec de cursor opaco `base64url(inicio|id)`; tests `test_fallidas_query_campo_extra_400` y `test_cursor_invalido_400` (capa: schemas/API)
- [x] 7.2 Implementar la consulta keyset con columnas explícitas, `ORDER BY t.inicio DESC, n.id DESC`, comparación de tupla parametrizada, exclusión de `turno_cancelado` y `LIMIT limit+1`; tests `test_fallidas_lista_solo_fallos_smtp`, `test_fallidas_orden_por_inicio_descendente` y `test_fallidas_keyset_devuelve_next_cursor` (capa: DB real)
- [x] 7.3 Exponer `GET /api/notificaciones/fallidas` con `require_role("recepcion", "admin")` y respuesta `{items, next_cursor}` con los campos de D-9; tests `test_fallidas_recepcion_200`, `test_fallidas_odontologo_403` y `test_fallidas_sin_sesion_401` (capa: API/DB)
- [x] 7.4 Verificar que la respuesta no expone `SMTP_PASS` ni campos extra y que el endpoint aparece en el OpenAPI; tests `test_fallidas_no_expone_secretos` y `test_openapi_incluye_endpoint_fallidas` (capa: API/contrato)

## 8. Integración y cierre

- [x] 8.1 Test end-to-end: reserva con `service.reservar` de C-05 + `run_once` inmediato envía la confirmación (≤ un ciclo, <5 min) y deja la notificación `enviada`; test `test_reserva_confirmacion_se_envia_en_el_siguiente_ciclo` (capa: DB real + sender fake)
- [x] 8.2 Correr `python -m pytest backend/tests -q` y `python -m ruff check backend`; verificar 0 fallos y sin regresiones de C-01..C-05 (capa: integración; pegar salida en `apply-log.md`)
- [x] 8.3 Verificar que no hay migraciones nuevas (`git status --short` sin `backend/alembic/versions/`) y que `alembic current` sigue en `002_agenda_meta (head)` (capa: schema)
- [x] 8.4 Correr `openspec validate c-08-notificaciones-mail-worker --strict` y `openspec status --change c-08-notificaciones-mail-worker --json`; registrar salidas en `apply-log.md` (capa: proceso)
- [x] 8.5 Revisar `git status --short` y confirmar que el alcance se limita a `backend/app/modules/notificaciones/`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/requirements.txt`, `.env.example`, `backend/tests/` y el change (capa: alcance; sin commit)

## Workflow follow-up

- Revisión humana obligatoria (governance ALTO): D-2 (índice/consulta JSONB), D-3 (concurrencia/lock), D-5 (SMTP/sender), D-7 (lifespan), D-8 (descarte) y D-9 (contrato del panel).
- Después de la revisión: `/opsx:archive c-08-notificaciones-mail-worker` y marcar `[x]` en `CHANGES.md` bajo orden explícita.
- Coordinación con C-12: cron/worker del host, backups y Gmail definitivo quedan fuera de C-08.

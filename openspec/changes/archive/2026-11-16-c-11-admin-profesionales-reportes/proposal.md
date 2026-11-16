# Proposal — c-11-admin-profesionales-reportes

## Why

US-010 y US-011 siguen sin implementar: el consultorio no puede dar de alta ni de baja profesionales y usuarios staff sin tocar la base a mano (hoy solo existen por seed), y no hay ninguna vista de ocupación/ausentismo para detectar huecos. `backend/app/modules/reportes/router.py` es un stub vacío y `backend/app/modules/profesionales/router.py` solo expone el catálogo público y la agenda. Con C-07/C-10 ya operativos, la falta de administración de profesionales/usuarios y de reporte es lo que impide operar el consultorio sin soporte técnico.

## What Changes

- **CRUD admin de profesionales** sobre `/api/profesionales`: alta con `duracion_default_min` configurable, edición de datos y duración, baja = `activo=false` (nunca borrado físico en v1), reactivación, y listado admin con `?incluir_inactivos=true`. El catálogo público (`GET /api/profesionales` sin flag) no cambia: mismas columnas explícitas (sin `activo`) y sin resolver sesión, así que una cookie inválida o vencida no convierte el `200` público en `401`.
- **Baja de profesional sin guarda de turnos futuros** (US-010 CA-2): `DELETE` y `PUT {"activo": false}` hacen soft-delete siempre (`200`), conservando turnos históricos, disponibilidades y bloqueos. Los turnos futuros `reservado`/`confirmado` quedan intactos y siguen siendo gestionables por staff; el profesional inactivo sale del catálogo público y del alta de reservas. La salida operativa es cancelar y volver a reservar; la reasignación entre profesionales no existe en v1 (PB-08).
- **CRUD admin de usuarios staff** en `/api/usuarios-staff`: alta con `rol` y `profesional_id` opcional, edición de rol/link/activo, baja lógica y reactivación. Invariante `rol=odontologo ⇔ profesional_id` obligatorio; `recepcion`/`admin` sin link; en `PUT`, un `profesional_id` nuevo debe existir y estar activo (`422` en el campo) sin revalidar el vínculo cuando el patch no lo trae. `password_hash` nunca sale en respuestas. La regla "nunca cero admins activos" (`422 ultimo_admin`, aplicada a `DELETE` y a `PUT` con `activo=false`/degradación) es una convención del proyecto por riesgo de lockout, no una regla de la KB.
- **`GET /api/reportes/ocupacion?desde=&hasta=&profesional_id=`**: tabla por profesional con `turnos`, `atendidos`, `ausentes`, `cancelados`, `pendientes`, `minutos_ocupados`, `minutos_disponibles` y `porcentaje_ocupacion`, más una fila de `totales`; filtro por rango de fechas inclusivo en TZ `America/Argentina/Buenos_Aires` con tope de 366 días (`(hasta-desde).days + 1`), error `400` siempre en `campo="hasta"`. La capacidad se calcula con la configuración vigente al momento de la consulta; una fila sin turnos informa contadores en cero y `porcentaje_ocupacion=null` cuando la capacidad es cero. RBAC: admin y recepción ven todos; odontólogo solo su propia fila.
- **GATE PB-06 FINAL respetado**: la respuesta es una tabla JSON; **no hay export CSV** en v1 (`format`/`csv` como parámetro desconocido → `400` por campo).
- Sin migración Alembic (`head` sigue en `002_agenda_meta`): se reutilizan `profesional`, `usuario_staff`, `turno`, `disponibilidad` y `bloqueo` con sus índices actuales.
- Todos los bodies/queries con `extra='forbid'` → `400` con detalle por campo; `401` sin sesión y `403` genérico por rol; queries parametrizadas y columnas explícitas (sin `SELECT *`, sin `OFFSET`).

## Capabilities

### New Capabilities

- `admin-profesionales`: ciclo de vida admin del profesional (alta, edición, `duracion_default_min`, baja lógica conservando historial y turnos futuros, reactivación y listado admin con inactivos).
- `reportes-ocupacion`: reporte tabular de ocupación/ausentismo por profesional y período, con definición exacta de métricas, semántica de rango/TZ y alcance por rol.

### Modified Capabilities

- `staff-auth`: se agrega la gestión de usuarios staff por parte del admin (alta con rol y `profesional_id`, edición, baja lógica con guardas, reactivación y efecto inmediato de la baja sobre sesiones vigentes). No cambia el contrato de login/logout ni las dependencias `require_role`/`require_own_profesional` existentes.

## Impact

- Backend nuevos: `backend/app/modules/usuarios_staff/{router,service,schemas}.py`, `backend/app/modules/reportes/{router,service,schemas}.py` y `backend/app/modules/profesionales/{schemas,service}.py`.
- Backend extendido: `backend/app/modules/profesionales/router.py` (alta/edición/baja + flag `incluir_inactivos` reutilizando la sesión opcional de `agenda/public.py`, resuelta sólo en la rama admin), `backend/app/modules/agenda/schemas.py` (`ProfesionalesQuery.incluir_inactivos`), `backend/app/main.py` (montar el router nuevo de usuarios staff).
- API: nuevas rutas `POST/PUT/DELETE /api/profesionales`, `GET/POST/PUT/DELETE /api/usuarios-staff` y `GET /api/reportes/ocupacion`; el contrato público de `GET /api/profesionales` y `GET /api/profesionales/{id}/agenda` no cambia.
- DB: sin migración ni cambios de modelo; `alembic upgrade head` no cambia.
- Frontend: **fuera de alcance** — C-11 entrega API/admin backend. La pantalla admin de profesionales/usuarios y el reporte renderizado no tienen change asignado en v1 (ver Risegos).
- Tests nuevos: `backend/tests/test_admin_profesionales.py`, `test_usuarios_staff_admin.py`, `test_reportes_ocupacion.py`, `test_reportes_rbac.py` (Postgres real, datos ficticios).
- Fuera de alcance: export CSV/Excel (PB-06), reset/change de password staff (post-v1, C-03), borrado físico de profesionales o usuarios, auditoría genérica de administración (v1 solo audita mutaciones de turnos), edición de disponibilidades/bloqueos desde admin, y reprogramación entre profesionales (PB-08/v1.1).
- Gobernanza: **MEDIO**. Riesgos principales: un cambio de `duracion_default_min` que desalinee turnos ya reservados, una baja o degradación de usuario que deje el sistema sin admin, y un turno futuro que quede con su profesional inactivo. Mitigación: los turnos conservan su `duracion_min` propia; "nunca cero admins activos" (`422 ultimo_admin` sobre el estado resultante con bloqueo ordenado de las filas admin, en `DELETE` y en `PUT`); y la baja no bloquea ni cancela turnos, sino que los deja intactos y gestionables por staff (cancelar y re-reservar, sin reasignación en v1).

# Design — c-11-admin-profesionales-reportes

## Context

Ver `proposal.md` (§Why). Estado relevante del repo:

- `backend/app/modules/profesionales/router.py` ya expone el catálogo público keyset de activos y la agenda día/semana staff/pública; **no** hay escritura de profesionales. `ProfesionalesQuery` (`backend/app/modules/agenda/schemas.py`) es `extra='forbid'` con `limit`/`cursor`.
- `backend/app/modules/reportes/router.py` es un stub con solo el `APIRouter(prefix="/api/reportes")`; `backend/app/main.py` ya lo monta.
- `backend/app/modules/auth/deps.py` provee `get_current_staff`, `require_role(*roles)` (admin siempre pasa) y `require_own_profesional`; `agenda/public.py` provee `staff_opcional` y `parse_query_or_400` (400 por campo). `core/security.py` provee `hash_password` (argon2id).
- `agenda/slot_service.py` computa la grilla real de slots (`compute_slots`, half-open `[)`), y ya lee `disponibilidad` (con `vigente_desde`/`vigente_hasta`), `bloqueo` y turnos activos con columnas explícitas.
- Modelos: `profesional` (`activo`, `duracion_default_min` default 30, `ultima_actualizacion` mantenida por trigger **solo** de `disponibilidad`/`bloqueo`), `usuario_staff` (`email CITEXT UNIQUE`, `rol` enum `recepcion|odontologo|admin`, `profesional_id` nullable, `activo`), `turno` (`estado` enum RN-TU-07, `duracion_min` por fila, FK `ON DELETE RESTRICT`).
- Índices existentes: `ix_turno_prof_inicio (profesional_id, inicio)`, parcial `ix_turno_estado_inicio` (solo reservado/confirmado), parcial `ix_profesional_activo`, `ix_disponibilidad_prof_dia`, `ix_bloqueo_profesional_id`, `ix_usuario_staff_profesional_id`.
- Alembic `head = 002_agenda_meta`. C-07/C-10 ya archivados; C-11 es backend/admin API.

## Goals / Non-Goals

**Goals:**

- Agregar escritura admin de profesionales y usuarios staff reutilizando las dependencias de C-03 y los índices/modelos existentes, sin tocar el contrato público de agenda.
- Fijar una baja de profesional que nunca pierda historial y que no se bloquee por turnos futuros: la baja es siempre `activo=false` y los turnos futuros quedan intactos y gestionables por staff.
- Fijar la identidad de usuario staff como invariante `rol=odontologo ⇔ profesional_id` para que el scoping de KB-03 siga siendo confiable.
- Definir el reporte de ocupación con una fórmula explícita y auditable (contadores + minutos), reutilizando la grilla de slots como denominador.
- Mantener todo dentro de `extra='forbid'`, queries parametrizadas, columnas explícitas y sin `OFFSET`.

**Non-Goals:**

- UI admin (pantallas de profesionales/usuarios/reportes): C-11 es API; no hay change de frontend admin en v1 (riesgo declarado).
- Export CSV/Excel (PB-06), paginación del reporte, reportes por obra social/profesional-fecha-slot, productividad o facturación.
- Reset/cambio de password staff, login social, MFA, borrado físico de profesionales/usuarios.
- Auditoría genérica de administración (RN-AU-02 solo cubre mutaciones de turno).
- Migraciones, columnas, enums, constraints o índices nuevos.
- Edición de disponibilidades/bloqueos desde admin, reasignación de turnos entre profesionales (PB-08/v1.1).

## Decisions

### D-1. Superficie HTTP, verbos y códigos

Qué:

| Método | Path | Rol | Éxito |
|---|---|---|---|
| `POST` | `/api/profesionales` | admin | `201` + `ProfesionalAdminOut` |
| `PUT` | `/api/profesionales/{id}` | admin | `200` + `ProfesionalAdminOut` |
| `DELETE` | `/api/profesionales/{id}` | admin | `200` + `ProfesionalAdminOut` (`activo=false`) |
| `GET` | `/api/profesionales?incluir_inactivos=true` | admin | `200` + `items`/`next_cursor` |
| `GET` | `/api/usuarios-staff` | admin | `200` + `items`/`next_cursor` |
| `POST` | `/api/usuarios-staff` | admin | `201` + `UsuarioStaffOut` |
| `PUT` | `/api/usuarios-staff/{id}` | admin | `200` + `UsuarioStaffOut` |
| `DELETE` | `/api/usuarios-staff/{id}` | admin | `200` + `UsuarioStaffOut` (`activo=false`) |
| `GET` | `/api/reportes/ocupacion` | staff con alcance | `200` + `ReporteOcupacionOut` |

Errores: `400` por campo (body/query), `401` sin sesión, `403` genérico por rol, `404` id inexistente en rutas admin, `409` `email_duplicado`, `422` `ultimo_admin` y `422` por campo en la validación del vínculo de `PUT /api/usuarios-staff` (D-6). **No existe `409` por turnos futuros**: la baja lógica responde `200` siempre (D-4). Sin `204` (el proyecto devuelve cuerpo en los éxitos, como C-07).

Por qué: mantiene los paths que fija CHANGES (`/api/profesionales`, `/api/usuarios-staff`, `/api/reportes/ocupacion`) sin inventar `/admin/*`, y conserva el estilo de códigos ya usado por C-05/C-06/C-07.

Alternativas descartadas: `/api/admin/...` (duplica recursos ya existentes); `PATCH` para la edición de profesional (el proyecto usa `PUT` con campos opcionales, p. ej. reprogramación C-07); `204` en bajas (rompe el patrón de respuesta con recurso).

### D-2. RBAC y alcance por rol

Qué:

- Escrituras de profesionales y todo `/api/usuarios-staff`: `require_role("admin")` (admin pasa; `recepcion`/`odontologo` → `403`; sin sesión → `401`).
- `GET /api/profesionales?incluir_inactivos=true`: el flag se evalúa **antes** de tocar la sesión. Sin flag → rama pública intacta (`200`, sin resolver sesión). Con flag → rama admin: `staff_opcional` recién ahí; sin sesión o con cookie inválida/vencida → `401`; con sesión no admin → `403`. Un valor no booleano → `400` por campo vía `profesionales_query`, también antes de cualquier acceso a sesión.
- Reporte: dependencia propia `alcance_reporte(staff, profesional_id)`:
  - `admin`/`recepcion` → alcance total; `profesional_id` opcional actúa como filtro.
  - `odontologo` → si `staff.profesional_id is None` → `403`; si viene `profesional_id` distinto del propio → `403` genérico; si coincide o no viene → alcance `[propio]`.
  - sin sesión → `401`.

Por qué: KB-03 es el contrato (admin todo, recepción básicos, odontólogo propios) y RN-AU-01 excluye ABAC. Se reutilizan las dependencias de C-03 en vez de duplicar lógica; el caso "flag admin sobre endpoint público" es el único que necesita sesión opcional. Resolver la sesión sólo en la rama admin es lo que garantiza que una cookie inválida o vencida **no** convierta un `200` público en `401` (H-03).

Alternativas descartadas: endpoint `/api/profesionales/admin` separado (inventa ruta y duplica keyset); permitir que un odontólogo pase cualquier `profesional_id` y devolver `403` con datos parciales (fuga de existencia/actividad); resolver sesión en ambas ramas (una cookie vencida rompe el catálogo público).

### D-3. Alta y edición de profesional; semántica de `duracion_default_min`

Qué:

- `ProfesionalCreate`: `nombre` obligatorio 1–120 (trim, vacío → 400), `matricula` 1–50 opcional, `especialidad` 1–100 opcional, `duracion_default_min` default 30, `ge=5`, `le=240`, `multiple_of=5`. `extra='forbid'`. El rango 5–240 múltiplo de 5 es una **convención del proyecto** (no deriva de la KB): la granularidad de slots de RN-AG-02 exige múltiplos de 5 y el tope de 240 evita grillas absurdas de más de 4 h por turno; se justifica y testea en los bordes 5 y 240 (ver D-16).
- `ProfesionalUpdate`: mismos campos + `activo: bool | None`, todos opcionales, `extra='forbid'`, validador "al menos uno" → 400 `campo="body"`.
- `ProfesionalAdminOut`: `id`, `nombre`, `matricula`, `especialidad`, `duracion_default_min`, `activo`, `ultima_actualizacion`. Nunca turnos ni conteos.
- `duracion_default_min` solo define la grilla de slots **futura**; cada `turno` conserva su `duracion_min` propia (C-02). Cambiarlo no reescribe turnos: la disponibilidad seguirá mostrando el turno con su duración real y la ventana libre se computa por intervalos (`compute_slots`), por lo que no aparece solape.
- `matricula` **no** se hace única: KB-04 no lo exige y agregar un índice único parcial requeriría migración. Duplicados posibles = deuda aceptada y documentada (validación manual de recepción).
- `ultima_actualizacion` no se toca en alta/edición: el trigger `touch_profesional_updated` solo reacciona a `disponibilidad`/`bloqueo` (migración 002); su semántica es "frescura de la agenda", no `updated_at` genérico.

Por qué: fija un rango de duración coherente con RN-AG-02 (granularidad de slots) y evita que un cambio de duración corrompa la agenda ya reservada. No migrar mantiene el change MEDIO y el `head` estable.

Alternativas descartadas: recalcular `duracion_min` de turnos futuros al cambiar el default (reescribe reservas y puede provocar solapes); `duracion_default_min` libre 1–1440 (genera grillas absurdas); unicidad de matrícula con migración 003 (fuera de scope, dato informativo en v1).

### D-4. Baja de profesional: lógica, turnos futuros y concurrencia

Qué:

1. `DELETE` (y `PUT {"activo": false}`) ejecutan el mismo `dar_de_baja()`:
   - `SELECT id, activo FROM profesional WHERE id=:id FOR UPDATE` (columnas explícitas, parámetro ligado); si no existe → `404`.
   - Si ya está `activo=false` → `200` idempotente, sin más comprobaciones.
   - `UPDATE profesional SET activo=false`; commit.
   - **No hay guarda por turnos futuros.** La baja responde `200` siempre, haya o no turnos `reservado`/`confirmado` con `inicio` futuro. US-010 CA-2 define la baja como `activo=false` que conserva historial, sin precondiciones; RN-TU-03 es anti-solape, no una guarda de baja.
2. Los turnos futuros existentes **quedan intactos** (estado, `inicio`, `duracion_min`) y siguen siendo gestionables por staff: la agenda por `profesional_id` sigue respondiendo `200` para staff (la regla de que el `404` por inactividad no aplica a staff ya existe en `agenda-disponibilidad`), y recepción puede cancelarlos por la vía de C-07. El profesional inactivo deja de ofrecerse en el catálogo público y en el alta de reservas.
3. Salida operativa v1 para un turno futuro de un profesional dado de baja: **cancelar el turno y volver a reservar** con otro profesional (cancelación C-07, reserva C-06/C-05). La reprogramación de C-07 mueve fecha/duración conservando el profesional, así que no reasigna; la reasignación entre profesionales y la reprogramación por paciente **no existen en v1** (PB-08): C-11 no las inventa ni cancela turnos automáticamente en la baja.
4. **Nunca** borrado físico: no hay `?fisico`, no se toca `turno`, `disponibilidad`, `bloqueo` ni `usuario_staff`. Un parámetro de query no declarado (`?fisico=true`) → `400` por campo (queda explícito que no existe la variante física).
5. Concurrencia: `dar_de_baja()` bloquea la fila `profesional` con `FOR UPDATE`, el mismo primer lock que usa la reserva de C-05 (que bloquea el profesional antes de computar slots y rechaza profesionales inactivos). Así baja y reserva se serializan:
   - Si la reserva entra primero, el turno nuevo queda y la baja igual procede (`200`), dejando un turno futuro intacto y gestionable por staff.
   - Si la baja entra primero, la reserva ve `activo=false` y falla según el contrato de C-05.
   - Nunca hay `500` ni un turno activo apuntando a un profesional borrado (`turno.profesional_id` es FK `RESTRICT`).
6. `activo=false` no desactiva el `usuario_staff` vinculado: son identidades separadas (un odontólogo puede seguir logueado para consultar historial). Riesgo declarado y acción manual del admin.

Por qué: la KB fija la baja como deactivación sin precondiciones; bloquearla por turnos futuros agrega una regla que la KB no tiene y deja al consultorio sin poder desactivar a un profesional que se fue. Los turnos futuros no quedan huérfanos de operación porque staff los sigue viendo y gestionando, y la salida (cancelar y re-reservar) ya existe. El lock del profesional elimina la carrera con la reserva sin introducir un lock de tabla.

Alternativas descartadas: `409` con turnos futuros (regla no respaldada por la KB, obliga a operar los turnos antes de poder dar de baja); cancelar automáticamente los turnos futuros en la baja (destructivo, encola notificaciones masivas y mezcla dos operaciones en una); reprogramar/reasignar automáticamente (PB-08 lo deja fuera de v1); borrado físico cuando no hay turnos (requiere borrar disponibilidades/bloqueos y pierde trazabilidad; la regla dura 3 permite el físico con cero turnos, pero no lo exige, y v1 no lo ofrece).

### D-5. Listado admin con inactivos sin cambiar el contrato público

Qué: `ProfesionalesQuery` suma `incluir_inactivos: bool = False`. El handler evalúa el flag **antes** de resolver sesión:

- Sin el flag → rama pública idéntica a hoy: no se resuelve sesión, `WHERE activo IS TRUE`, columnas explícitas `id, nombre, especialidad, matricula, duracion_default_min, ultima_actualizacion` (**sin `activo`**), keyset por `id`, `limit`/`cursor`.
- Con `incluir_inactivos=true` → rama admin: recién ahí se resuelve la sesión con `staff_opcional`; sin sesión o con cookie inválida/vencida → `401`; con sesión no admin → `403`; con admin → `WHERE` sin filtro de `activo` y serializer admin `ProfesionalAdminOut` que **sí** incluye `activo`.
- Un valor no booleano del flag → `400` por campo vía `profesionales_query`, antes de cualquier acceso a sesión.
- La respuesta pública queda **exactamente** como hoy (spec `agenda-disponibilidad`, columnas explícitas sin `activo`); el serializer admin es exclusivo de la rama admin.

Por qué: es el mínimo cambio compatible: cualquier cliente público actual sigue funcionando (flag ausente) y el admin obtiene la vista que necesita para reactivar. Resolver la sesión sólo en la rama admin evita que una cookie inválida/vencida convierta un `200` público en `401`. Se documenta como requisito de `admin-profesionales`, no como cambio del requisito público de `agenda-disponibilidad`.

Alternativas descartadas: endpoint admin de listado (`/api/profesionales/todos`) con una segunda implementación de keyset; agregar `activo` a las filas públicas para reutilizar un serializer (rompe el contrato verificado de `agenda-disponibilidad` y expone estado interno a clientes anónimos); devolver inactivos siempre (rompe la semántica pública y C-09/C-10).

### D-6. Alta de usuario staff, invariante de rol y hash

Qué:

- Nuevo módulo `backend/app/modules/usuarios_staff/` (`router.py`, `schemas.py`, `service.py`) montado en `main.py`; se importa `hash_password` de `core/security.py` y `require_role("admin")` de `auth/deps.py`.
- `UsuarioStaffCreate`: `email` (mismo patrón que login, 3–320), `password` 8–256, `rol: StaffRol`, `profesional_id: UUID | None`. `extra='forbid'`. Los umbrales 3–320 y 8–256 son **convenciones del proyecto** (no derivan de la KB): 3–320 sigue el máximo práctico de email y el mínimo que descarta cadenas vacías/inútiles; 8–256 fija un mínimo razonable sin complejidad obligatoria y un tope anti-DoS de hashing. Se testean los bordes 3/320 y 8/256 (ver D-16).
  - Invariante en schema: `rol=="odontologo"` exige `profesional_id`; `recepcion|admin` lo prohíben → 400 `campo="profesional_id"`.
  - Servicio: el profesional debe existir y estar `activo=true` → si no, 400 `campo="profesional_id"` (es un campo del body del alta, no una lectura de recurso).
  - `password_hash = hash_password(password)` (argon2id); nunca se loguea ni se devuelve.
  - Unicidad: pre-check por `email` (CITEXT compara sin distinguir mayúsculas) para un 409 amable y `IntegrityError` de `usuario_staff_email_key` mapeado a `409 email_duplicado` para la carrera.
- `UsuarioStaffUpdate`: `rol`, `profesional_id`, `activo`, opcionales, al menos uno, `extra='forbid'`. `email` y `password` son claves desconocidas → 400 por campo (email inmutable, sin reset en v1). El invariante se valida sobre el estado **resultante** (`actual + patch`), no sobre el patch: cambiar a `recepcion` sin mandar `profesional_id=null` → 400 `campo="profesional_id"`.
- Validación del vínculo en `PUT`: cuando el patch trae `profesional_id` no nulo, el servicio resuelve el profesional y exige que **exista y esté `activo=true`**; si no existe o está inactivo → `422` con `detail.campo="profesional_id"` (la referencia se resuelve en la transición de estado, no es un campo nuevo del body; a diferencia del alta, que responde `400` por ser validación de body, duro 1). Si el patch **no** trae `profesional_id`, el vínculo existente **no se revalida**: editar `rol`, `activo` u otros campos de un usuario ya vinculado a un profesional desactivado responde `200` (conserva su link histórico; su agenda simplemente no recibe turnos nuevos).
- `PUT {"activo": false}` sobre el último admin activo → `422 ultimo_admin` (misma guarda que `DELETE`, ver D-7).
- `UsuarioStaffOut`: `id`, `email`, `rol`, `profesional_id`, `activo`. Sin `password_hash`.
- Listado: `GET /api/usuarios-staff?limit=&cursor=` keyset por `id`, **incluye activos e inactivos** (es admin-only; el admin necesita ver para reactivar), orden `id`, columnas explícitas, `LIMIT limit+1`, sin `OFFSET`.
- Sin restricción de "un usuario por profesional": dos odontólogos linkeados al mismo profesional comparten agenda (escala <50); documentado.

Por qué: el invariante rol↔link es lo que hace confiable `require_own_profesional`; validarlo en el estado resultante evita usuarios `odontologo` sin alcance (403 permanente) o `recepcion` con un link que no se usa. Argon2id ya es la política de C-03; 8 caracteres es un mínimo razonable sin complejidad obligatoria.

Alternativas descartadas: tabla de roles/permisos (RN-AU-01 lo excluye); `POST` con password opcional (permitiría usuarios sin login); devolver `password_hash` (innecesario y peligroso).

### D-7. Baja y degradación de usuario staff: regla "siempre un admin activo"

Qué:

> La regla "nunca cero admins activos" es una **convención del proyecto**, no deriva de la KB: RN-AU-01 fija la gestión exclusiva de admin, no un mínimo de administradores. Se adopta por el riesgo operativo real (lockout): si se desactiva o degrada la última cuenta admin, el consultorio queda sin administración y sólo se recupera tocando la DB.

- `DELETE /api/usuarios-staff/{id}`: `SELECT ... FOR UPDATE` del destino (404 si no existe), luego la guarda común, luego `activo=false` y commit. El texto `no_auto_baja` no existe como caso especial: un admin puede darse de baja a sí mismo si queda otro admin activo (operación legítima al dejar el consultorio) y es rechazado cuando es el último.
- `PUT /api/usuarios-staff/{id}` con `rol` o `activo=false` que afecten la administración: misma guarda antes de persistir. `PUT {"activo": false}` sobre el último admin activo → `422 ultimo_admin`, igual que `DELETE`.
- Guarda común `asegurar_admin_restante(db, destino, cambio)`:
  1. Leer el destino sin lock (solo para 404 y rol actual).
  2. Bloquear el conjunto admin **primero y siempre en el mismo orden**: `SELECT id, rol, activo FROM usuario_staff WHERE rol='admin' AND activo ORDER BY id FOR UPDATE`. Este es el único punto de serialización; el lock del destino no se toma antes para no crear un ciclo (A bloquea a B y B a A) en la carrera de bajas mutuas.
  3. Si el destino no está en ese conjunto (no es admin activo), bloquear su fila con `SELECT ... FOR UPDATE` y releerla para evitar carreras con reactivaciones.
  4. Aplicar el cambio en memoria sobre el conjunto y exigir al menos un admin activo restante; si queda vacío → `422 ultimo_admin` y rollback sin cambios.
- La guarda se evalúa sobre el **estado resultante**, no sobre "el destino es el último": así cubre auto-baja, auto-degradación, `PUT {"activo": false}` y las carreras de dos admins operando en simultáneo. Como `PUT` y `DELETE` toman el **mismo lock ordenado** sobre las filas admin, `PUT activo=false` × `DELETE` y `PUT` × `PUT` serializan igual: el segundo ve el resultado del primero y recibe `422` si dejaría cero admins activos.
- Idempotencia: repetir `DELETE` sobre un destino ya inactivo → `200` sin efectos; la guarda no cambia el conteo y pasa.
- Efecto inmediato: no se toca la denylist de `jti`; `get_current_staff`/`staff_opcional` cargan el usuario y verifican `activo`, por lo que el siguiente request del usuario dado de baja responde `401` aunque su JWT siga vigente, y un admin auto-degradado recibe `403` en rutas admin aunque su JWT diga `admin`. No hay cambio en `auth/` (comportamiento ya implementado).
- Reactivación: `PUT {"activo": true}`; el login vuelve a funcionar con la password previa. Reutilizar un email requiere esta vía (409 en `POST`), por la unicidad CITEXT.

Por qué: una sola regla verificable ("nunca cero admins activos") elimina el bloqueo operativo real, cubre el hueco de la auto-degradación por `PUT` (que la sola guarda de auto-baja no cubre) y usa la autoridad de la DB ya existente en lugar de inventar revocación de sesión por usuario.

Alternativas descartadas: borrado físico de usuarios (rompe FKs de `bloqueo.creado_por`/`auditoria_turno.actor_id` y pierde trazabilidad); denylist por usuario (C-03 es in-process y la DB ya resuelve); guarda `no_auto_baja` separada (redundante y no cubre `PUT`); prohibir toda auto-baja aunque queden otros admins (impide una salida legítima sin ganancia de seguridad).

### D-8. Contrato del reporte de ocupación

Qué:

- `ReporteOcupacionQuery` (`extra='forbid'`): `desde: date`, `hasta: date`, `profesional_id: UUID | None = None`. La validación del rango vive en un **validador de campo sobre `hasta`** que conoce `desde` (`ValidationInfo`/`model_validator(mode="after")` mapeado explícitamente a `campo="hasta"`), **no** en un `model_validator` genérico: ese devolvería `campo="query"` y el contrato exige el campo puntual. Reglas: `desde <= hasta` y tope **inclusivo** `(hasta - desde).days + 1 <= 366`; toda violación → `400` con `detail.campo="hasta"`. Tests exactos del tope: 366 días → `200`, 367 días → `400`. Fechas inválidas o ausentes, o `profesional_id` malformado → `400` por campo vía `parse_query_or_400`.
- Respuesta `ReporteOcupacionOut`:
  ```json
  {
    "desde": "2026-11-02",
    "hasta": "2026-11-08",
    "zona": "America/Argentina/Buenos_Aires",
    "items": [
      {
        "profesional": {"id": "…", "nombre": "…", "activo": true},
        "turnos": 4, "atendidos": 1, "ausentes": 1,
        "cancelados": 1, "pendientes": 1,
        "minutos_ocupados": 90, "minutos_disponibles": 180,
        "porcentaje_ocupacion": 50.0
      }
    ],
    "totales": { "turnos": 4, "atendidos": 1, "ausentes": 1, "cancelados": 1,
                 "pendientes": 1, "minutos_ocupados": 90,
                 "minutos_disponibles": 180, "porcentaje_ocupacion": 50.0 }
  }
  ```
- `profesional_id` inexistente → `200` con `items=[]` y `totales` en cero (es un filtro, no una lectura de recurso).
- Sin export: `format`, `csv`, `xlsx` son claves desconocidas → 400 por campo (PB-06).

Por qué: un contrato plano y numérico permite que un futuro frontend (o un cliente) arme la tabla sin lógica de negocio; `totales` hace verificable el "cuadre" que pide el gate y sirve de sanity check para el admin.

Alternativas descartadas: devolver solo el total o solo porcentajes (no permite auditar el cuadre); paginar filas (los profesionales son <50 y la regla dura 7 prohíbe `OFFSET` en reportes).

### D-9. Definición exacta de métricas y denominador

Qué, para cada profesional del alcance:

- **Rango de turnos**: `inicio ∈ [desde 00:00, (hasta+1 día) 00:00)` en `America/Argentina/Buenos_Aires`, convertido a UTC para comparar contra `turno.inicio` (`timestamptz`).
- `turnos` = cantidad de turnos en el rango, **todos los estados**.
- `atendidos`/`ausentes`/`cancelados` = conteos por `estado` (RN-TU-07).
- `pendientes` = `turnos - atendidos - ausentes - cancelados` (agrupa `reservado` + `confirmado`, derivado del agregado, sin cuarta consulta).
- `minutos_ocupados` = `SUM(duracion_min)` de los turnos en estados `reservado`, `confirmado`, `atendido`, `ausente`. `cancelado` no suma ocupación: liberó el slot.
- `minutos_disponibles` = **capacidad ofrecible**: se reutiliza `slot_service.compute_slots(ventanas, bloqueos, [], duracion_default_min, desde, hasta, TZ)` (sin turnos) y se toma `len(slots) * duracion_default_min`. Esto respeta `vigente_desde`/`vigente_hasta`, resta bloqueos y usa la misma grilla que la reserva (RN-AG-02), así el denominador es comparable con lo que la agenda realmente ofrece. **La capacidad se calcula con la configuración vigente al momento de la consulta** (duración default actual y disponibilidad/bloqueos actuales): no se reconstruye la configuración histórica del rango. Profesional sin ventanas vigentes en el rango → `0`.
- `porcentaje_ocupacion` = `round(minutos_ocupados / minutos_disponibles * 100, 1)` si `minutos_disponibles > 0`; si no, `null`. **No se recorta** a 100: un valor >100 señala turnos forzados fuera de ventana (recepción) y es información útil, no un error.
- `totales` = suma de cada contador/minutos y `%` recalculado sobre las sumas (mismo criterio de `null`).
- Fila sin turnos: todos los contadores en `0`, `minutos_ocupados=0` y `porcentaje_ocupacion` resuelto por la misma regla (`0.0` si hay capacidad, `null` si `minutos_disponibles=0`). Aplica tanto a un profesional activo incluido por alcance total como a un `profesional_id` filtrado que no tiene turnos.
- Filas incluidas: con alcance total, todos los profesionales `activo=true` **más** los inactivos que tengan ≥1 turno en el rango (para no perder historial), y **siempre** la fila de un `profesional_id` filtrado aunque no tenga turnos (activo o inactivo); con alcance de odontólogo, solo la fila propia. Orden determinista: `nombre, id`.
- La capacidad usa el `duracion_default_min` **actual** del profesional (es la grilla que se ofrece hoy); los turnos viejos aportan su propia `duracion_min` al numerador.

Por qué: la fórmula debe poder explicarse en una frase al dueño del consultorio ("de las horas que ofrecí, cuántas quedaron tomadas"), y debe coincidir con la grilla que el sistema realmente ofrece hoy, no con minutos teóricos de ventana (que sobrestiman cuando la ventana no es múltiplo de la duración). Incluir `ausente` en ocupación refleja que el slot no se pudo reutilizar; el ausentismo se lee aparte. Calcular la capacidad con la configuración vigente hace el reporte reproducible como consulta de "capacidad actual sobre un período pasado" y evita inventar versionado histórico de disponibilidad.

Alternativas descartadas: denominador = minutos de ventana sin descontar bloqueos ni ajustar a la grilla (sobrestima la capacidad y hace bajar artificialmente el %); numerador solo `atendido` (mezcla ocupación con efectividad y penaliza los turnos futuros del rango); recortar a 100 (oculta sobreasignación).

### D-10. Zona horaria, bordes y validación del rango

Qué: `TZ = ZoneInfo("America/Argentina/Buenos_Aires")` como en `agenda/` y `profesionales/router.py`; los `date` de la query son días locales y se convierten a `datetime` aware con `tzinfo=TZ`, luego `.astimezone(UTC)` para el filtro SQL. Borde superior exclusivo (`hasta+1 día`). Un turno se imputa por `inicio` (no por `fin`), igual que la agenda día/semana. Rango invertido o tope inclusivo mayor a 366 días (`(hasta - desde).days + 1 > 366`) → `400` con `detail.campo="hasta"`, resuelto antes de ejecutar la consulta. La respuesta informa `zona` para que el cliente no asuma otra TZ.

Por qué: regla dura 10 (persistir UTC, mostrar/interpretar local) y consistencia con C-04/C-05, incluida la semántica half-open.

Alternativas descartadas: interpretar `desde`/`hasta` como UTC (corre el día 3 horas y rompe el reporte del día); aceptar datetimes con offset en la query (contrato innecesariamente amplio).

### D-11. Performance: agregación, columnas e índices

Qué:

1. Una query de turnos: `SELECT profesional_id, estado, count(*), sum(duracion_min) FROM turno WHERE inicio >= :desde_utc AND inicio < :hasta_utc [AND profesional_id = :pid] GROUP BY profesional_id, estado` — columnas explícitas, parámetros ligados, sin `SELECT *`.
2. Una query de profesionales en alcance: `SELECT id, nombre, activo, duracion_default_min FROM profesional WHERE … ORDER BY nombre, id`.
3. Lecturas acotadas de `disponibilidad` y `bloqueo` por profesional usando `fetch_ventanas`/`fetch_bloqueos` (o una variante batched equivalente con `IN`), siempre con columnas explícitas.
4. Cómputo de capacidad en Python con `compute_slots` sobre ≤366 días por profesional (bounded), fuera de la transacción de escritura.
5. Sin paginación ni `OFFSET` (regla dura 7): el conjunto de filas está acotado por la cantidad de profesionales.
6. Índices esperados: `ix_turno_prof_inicio` cuando hay `profesional_id`; el parcial `ix_turno_estado_inicio` no aplica al agregado de todos los estados; `ix_profesional_activo`, `ix_disponibilidad_prof_dia` y `ix_bloqueo_profesional_id` para las lecturas. Se adjunta evidencia `EXPLAIN` con volumen realista en la tarea de cierre; si mostrara un problema, el follow-up es una migración con índice sobre `turno (inicio)` o `(estado, inicio)` **fuera de C-11**.

Por qué: es el mínimo número de viajes a la DB y no depende de `N+1` por turno. Con el volumen v1 (decenas de profesionales, miles de turnos) el rango sigue siendo barato; medirlo antes de migrar respeta la regla de no migrar sin necesidad.

Alternativas descartadas: una query por profesional (N+1); agregación en Python trayendo turnos (`SELECT` de filas) en vez de `GROUP BY`; `generate_series` en SQL para la capacidad (más complejo y no reutiliza la grilla aprobada de C-04).

### D-12. Auditoría: alcance explícito

Qué: C-11 **no** escribe `AuditoriaTurno` ni ninguna otra tabla de auditoría. RN-AU-02 cubre mutaciones staff sobre turnos; `auditoria_turno` tiene FK a `turno` y trigger append-only, así que no aplica a profesionales/usuarios. Las mutaciones admin quedan trazadas solo por el estado persistido (`activo`) y los backups de C-12. Riesgo aceptado y declarado en `proposal.md`/`design.md`.

Por qué: inventar filas de auditoría sin turno violaría la FK/semántica; crear una tabla genérica de auditoría es un change propio (v1.1) con su propia governance.

Alternativas descartadas: reutilizar `auditoria_turno` con `turno_id` nulo (requiere migración y rompe la semántica); guardar JSON de cambios en `profesional` (columna nueva, migración).

### D-13. Sin migración

Qué: no se crean tablas, columnas, enums, constraints ni índices. Todo lo necesario existe: `profesional.activo/duracion_default_min/ultima_actualizacion`, `usuario_staff.email/rol/profesional_id/activo`, `turno.estado/duracion_min/inicio`, `disponibilidad` (incluye vigencia) y `bloqueo`. `alembic upgrade head` sigue en `002_agenda_meta`.

Por qué: el change es de API; agregar índices "por las dudas" viola la disciplina de migraciones y la regla dura 7 (índices se agregan si el EXPLAIN lo justifica).

Alternativas descartadas: índice único parcial de matrícula activa y índice de `turno (inicio)` en esta entrega (ver D-3/D-11; quedan como follow-up si hay evidencia).

### D-14. DB real, datos ficticios y sin reloj inyectable

Qué: C-11 no compara contra "ahora" (la baja no tiene guarda de turnos futuros y el reporte usa `desde`/`hasta` explícitos), así que **no** introduce un proveedor de reloj. Los turnos de prueba se crean con `inicio` fijo y explícito (sin `datetime.now()`), lo que mantiene los tests deterministas. Los tests de persistencia corren contra Postgres real (`db_session`/`test_engine`); los mocks quedan solo en el borde (`IntegrityError` forzado para el 409 de email). Emails `@cattaneo.test`, nombres y DNIs sintéticos; ningún dato real (duro 12). `ruff check` y `ruff format --check` obligatorios en el cierre.

Por qué: regla dura 9 (TDD, DB real cuando la persistencia es el sujeto) y tests deterministas sin depender del reloj del sistema.

Alternativas descartadas: `datetime.now()` directo para sembrar turnos (flaky); mocks de repositorio (duro 9); SQLite (no reproduce `CITEXT`, enums nativos, locks ni FKs).

### D-15. Límite de alcance: API sin UI admin

Qué: el change entrega endpoints y tests; no agrega pantallas. El reporte "tabla en pantalla" de PB-06 se resuelve como **respuesta tabular JSON**; no hay change de frontend admin en `CHANGES.md` (C-10 cubrió agenda staff y no incluye admin). Se deja el gap declarado como riesgo: para operar desde el navegador hará falta un change de UI admin o un ajuste de alcance humano antes de v1 en producción.

Por qué: el scope fijado por CHANGES para C-11 es "Admin (auth): CRUD … + GET /api/reportes/ocupacion"; adelantar UI cambiaría el tamaño del change y su governance (MEDIO).

Alternativas descartadas: incluir UI admin (scope creep, requiere tests Vitest, tipado estricto y mobile-first, y no está en el roadmap); devolver HTML desde el backend (rompe la arquitectura React de KB-08).

### D-16. Convenciones del proyecto (explícitas y no derivadas de la KB)

Estas reglas no salen de `knowledge-base/`; se fijan acá para que sean verificables y no se confundan con requisitos del dominio:

1. **Nunca cero admins activos** (D-7): justificación operativa de lockout, no una RN. Aplica a `DELETE` y a `PUT` con `rol="recepcion"` o `activo=false` sobre el último admin → `422 ultimo_admin`.
2. **`duracion_default_min` 5–240 múltiplo de 5** (D-3): granularidad de RN-AG-02 y tope anti-grillas absurdas. Bordes 5 y 240 aceptados; `0`, `-30`, `32`, `250` rechazados.
3. **`password` 8–256 y `email` 3–320** (D-6): mínimo práctico de password sin política de complejidad y tope anti-DoS de hashing; rango de email que descarta basura sin inventar RFC. Bordes 8/256 y 3/320 aceptados.
4. **Tope inclusivo de 366 días** en el reporte (D-8/D-10): `(hasta - desde).days + 1 <= 366`, testeado en 366 (200) y 367 (400).

Cada convención lleva al menos un test de borde en `tasks.md`; si el consultorio pide otro valor, se cambia acá y en su test, sin tocar la KB.

## Risks / Trade-offs

- **[Baja de profesional con turnos futuros activos]** → Trade-off aceptado: la baja procede siempre (`200`, `activo=false`) y los turnos futuros `reservado`/`confirmado` quedan intactos y gestionables por staff. Mitigación operativa: recepción cancela el turno (C-07) y se vuelve a reservar con otro profesional; la reasignación entre profesionales no existe en v1 (PB-08). No se automatiza la cancelación en la baja.
- **[Turno futuro de un profesional inactivo sin dueño inmediato]** → Mitigación: el turno sigue visible en la agenda por `profesional_id` (staff) y en los listados staff, así que es detectable y cancelable; el profesional inactivo deja de ofrecerse en el catálogo público y en el alta de reservas, por lo que no se generan turnos nuevos.
- **[Cambio de `duracion_default_min` desalinea turnos ya reservados]** → Mitigación: los turnos conservan su `duracion_min` y el cómputo de slots trata los intervalos ocupados, así que no hay solape; la grilla nueva solo aplica a turnos nuevos. Queda visible que un turno de 45' dentro de una grilla de 30' consume más que un slot.
- **[Baja de profesional no desactiva su usuario staff]** → Mitigación: son identidades separadas; el admin debe dar de baja el usuario. Documentado en design; el login del odontólogo sigue funcionando para consultar y operar los turnos ya existentes, aunque el profesional no reciba turnos nuevos.
- **[Sin reset de password]** → Mitigación: la reactivación conserva la password previa; si se perdió, la salida v1 es un procedimiento manual documentado (fuera de scope) o recrear con otro email. Deuda declarada (C-03 ya lo fijó post-v1).
- **[Matrícula no única]** → Mitigación: dato informativo en v1; recepción valida manualmente. Endurecerlo requiere migración y es follow-up.
- **[Email de usuario inactivo bloquea el alta de uno nuevo]** → Mitigación: `409` con indicación de reactivar la fila existente; es la consecuencia deliberada de la unicidad CITEXT sin borrado físico.
- **[Reporte sin índice dedicado para rango global]** → Mitigación: agregado único con `GROUP BY` y volumen v1 bajo; evidencia `EXPLAIN` en el cierre y follow-up de migración si el plan lo justifica.
- **[% de ocupación >100]** → Trade-off aceptado: señala turnos forzados fuera de ventana. El frontend futuro debe mostrar el valor tal cual, sin recortar.
- **[Sin UI admin]** → Mitigación: gap declarado; el API queda listo y testeado. Requiere decisión humana antes de producción (nuevo change de UI o uso vía API/herramientas).
- **[Sin auditoría de administración]** → Mitigación: no hay borrados físicos y C-12 hace backups; una tabla de auditoría genérica es follow-up v1.1.
- **[Locks y deadlocks]** → Trade-off: el orden `profesional → turno` y `usuario_staff` (admin rows) se mantiene estable; no se toman dos recursos en distinto orden dentro de C-11.

## Migration Plan

1. Sin migración: `alembic -c backend/alembic.ini heads` debe seguir mostrando una única head `002_agenda_meta`.
2. Deploy del backend con los routers nuevos (`usuarios_staff`, `reportes`) y el extendido de `profesionales`; verificar que `GET /api/profesionales` público y `GET /api/profesionales/{id}/agenda` responden igual que antes.
3. Rollback: redeploy sin las rutas nuevas. Los datos creados (profesionales/usuarios) se conservan; ninguna baja ejecutó borrado físico, por lo que no hay pérdida de historial. No ejecutar `downgrade`.

## Open Questions

- **UI admin**: si el consultorio necesita operar profesionales/usuarios y ver el reporte desde el navegador en v1, hace falta un change de frontend admin (no previsto en `CHANGES.md`); no cambia el contrato de API de este change.

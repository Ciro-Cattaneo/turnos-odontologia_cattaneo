# staff-auth Specification

## Purpose

Fija la frontera de confianza staff (recepción/odontólogo/admin): quién puede entrar (login por sesión), qué puede hacer cada rol (RBAC con scoping de odontólogo) y con qué garantías (hash verificado, cookie segura, sin enumeración, login limitado), antes de que cualquier write staff exista en C-04/C-07.

## Requirements

### Requirement: Login emite sesión en cookie httpOnly con rol

The system SHALL authenticate staff via `POST /api/auth/login` (email+password) and on success SHALL set a session cookie httpOnly carrying the role; the response SHALL NOT include the password hash.

#### Scenario: Login válido emite cookie con rol

- **DADO** un `UsuarioStaff` activo con email y hash vigentes
- **CUANDO** hace `POST /api/auth/login` con email+password correctos
- **ENTONCES** responde 200, emite cookie de sesión httpOnly con su rol y no expone `password_hash`

#### Scenario: EDGE — sesiones concurrentes en dos dispositivos coexisten

- **DADO** un staff ya logueado en un dispositivo
- **CUANDO** hace login desde un segundo dispositivo con las mismas credenciales
- **ENTONCES** ambas sesiones son válidas de forma independiente y el logout de una no invalida la otra

### Requirement: Schemas de login estrictos con extra forbid

The system SHALL validate the login body with strict Pydantic schemas (`extra='forbid'`) and SHALL return 400 with per-field detail on missing, malformed, or unknown fields.

#### Scenario: Body con campo desconocido es rechazado

- **DADO** el endpoint `POST /api/auth/login`
- **CUANDO** el body trae un campo extra no declarado (p. ej. `remember_me`)
- **ENTONCES** responde 400 con detalle del campo rechazado y no crea sesión

#### Scenario: Email con formato inválido es 400 en ese campo

- **DADO** el endpoint `POST /api/auth/login`
- **CUANDO** el body trae `email` sin formato válido o falta `password`
- **ENTONCES** responde 400 identificando el campo (`email` / `password`)

### Requirement: Errores de login genéricos sin enumeración

The system SHALL return an identical generic 401 message for unknown email, wrong password, and inactive account, with no timing or content signal distinguishing them.

#### Scenario: Usuario válido con password incorrecta es indistinguible de usuario inexistente

- **DADO** un email registrado y otro no registrado
- **CUANDO** se intenta login con password incorrecta en el primero y cualquier password en el segundo
- **ENTONCES** ambas respuestas son 401 con el mismo mensaje genérico y sin pistas de existencia

#### Scenario: Cuenta inactiva no revela su estado

- **DADO** un `UsuarioStaff` con `activo=false` y credenciales correctas
- **CUANDO** intenta `POST /api/auth/login`
- **ENTONCES** recibe el mismo 401 genérico que un login con password incorrecta

### Requirement: Logout invalida la sesión

The system SHALL invalidate the session cookie on `POST /api/auth/logout` so subsequent requests with that cookie are unauthenticated.

#### Scenario: Logout invalida y el reuse es 401

- **DADO** una sesión staff válida
- **CUANDO** hace `POST /api/auth/logout` y luego reusa la cookie anterior
- **ENTONCES** el logout responde 200 limpiando la cookie y el reuse posterior es 401

#### Scenario: EDGE — logout sin sesión es no-op seguro

- **DADO** una request sin cookie de sesión
- **CUANDO** hace `POST /api/auth/logout`
- **ENTONCES** responde 200 sin error ni fuga de información

### Requirement: Hash final con rotación al primer login y migración de semilla

The system SHALL verify passwords with the final scheme locked in design (bcrypt vs argon2), SHALL transparently rotate the transitory PBKDF2 seed hash to the final scheme on first successful login, and SHALL accept the rotated hash on subsequent logins.

#### Scenario: Login con hash semilla PBKDF2 rota al esquema final

- **DADO** un admin creado por seed con hash PBKDF2 transitorio (C-02) y password correcta
- **CUANDO** hace su primer `POST /api/auth/login`
- **ENTONCES** el login es 200 y su `password_hash` queda reescrito en el esquema final sin cambiar la password

#### Scenario: Login con hash ya rotado verifica directo

- **DADO** un staff cuyo hash ya está en el esquema final
- **CUANDO** hace `POST /api/auth/login` con su password
- **ENTONCES** verifica contra el esquema final en tiempo acotado y emite sesión

### Requirement: Cookie de sesión con flags seguros y expiración explícita

The system SHALL set the session cookie as httpOnly with SameSite/Secure flags per KB-08 and a defined lifetime; an expired session SHALL behave as unauthenticated (401).

#### Scenario: Cookie lleva flags httpOnly + SameSite y Secure según entorno

- **DADO** un login exitoso
- **CUANDO** se inspecciona la cookie de sesión emitida
- **ENTONCES** es httpOnly, con SameSite y Secure según lo fijado en design, y expira según el lifetime definido

#### Scenario: EDGE — sesión expirada es 401 sin mensaje interno

- **DADO** una cookie de sesión vencida según su lifetime
- **CUANDO** se usa contra un endpoint staff
- **ENTONCES** responde 401 genérico, indistinguible de no tener sesión

### Requirement: require_role con herencia Admin superset Recepción y lectura

The system SHALL enforce per-router authorization via the `require_role(...)` dependency with the KB-03 matrix: Admin ⊇ Recepción ⊇ lectura; odontólogo outside that chain (own agenda only).

#### Scenario: Matriz RBAC parametrizada por rol y recurso

- **DADO** las rutas staff protegidas y un usuario de cada rol (admin, recepción, odontólogo)
- **CUANDO** cada uno accede a lectura general, escritura de recepción y gestión admin
- **ENTONCES** admin accede a todo, recepción a todo menos gestión admin, y odontólogo solo a su agenda propia

#### Scenario: Odontólogo no ve agendas de otros profesionales

- **DADO** un odontólogo vinculado a `profesional_id = P1` y otro profesional P2 con turnos
- **CUANDO** pide la agenda de P2
- **ENTONCES** recibe 403 y ningún dato de P2 aparece en la respuesta

#### Scenario: Odontólogo sin profesional_id vinculado no accede a agendas

- **DADO** un odontólogo sin `profesional_id` asignado
- **CUANDO** pide cualquier agenda profesional
- **ENTONCES** recibe 403 genérico

### Requirement: Semántica 401 sin sesión vs 403 sin permiso

The system SHALL return 401 when no valid session exists and 403 when the session is valid but the role/scope lacks permission.

#### Scenario: Sin cookie hacia endpoint staff es 401

- **DADO** ningún token de sesión
- **CUANDO** se llama a cualquier endpoint staff sin cookie
- **ENTONCES** responde 401 y no revela si el recurso existe

#### Scenario: Rol insuficiente con sesión válida es 403

- **DADO** una sesión válida de recepción
- **CUANDO** accede a gestión exclusiva de admin (p. ej. CRUD usuarios-staff)
- **ENTONCES** responde 403 genérico con la sesión intacta

### Requirement: Rate-limit en login sin lockout permanente en v1

The system SHALL rate-limit `POST /api/auth/login` per IP (límite fijado en design) with 429 on excess, and SHALL NOT permanently lock accounts in v1 (no lockout-or-freeze; throttling only).

#### Scenario: Ráfaga de logins excede el límite y es 429

- **DADO** el límite de intentos por IP y ventana fijados en design
- **CUANDO** se supera con intentos repetidos de login
- **ENTONCES** responde 429 con reintento posterior permitido y sin bloquear la cuenta de forma permanente

#### Scenario: BUSINESS-ERROR — límite alcanzado no distingue credenciales

- **DADO** el rate-limit de login ya excedido para una IP
- **CUANDO** llega otro intento (válido o no)
- **ENTONCES** responde 429 con el mismo mensaje, sin indicar si las credenciales eran correctas

### Requirement: Alta de usuario staff con rol y vínculo profesional

The system SHALL expose admin-only `POST /api/usuarios-staff` to create a staff user with `email` (3–320), `password` (8–256), `rol` and optional `profesional_id`, enforcing `rol=odontologo ⇔ profesional_id` pointing to an active professional, and returning 201 without `password_hash`. (US-010, RN-AU-01, KB-04, duro 1.)

#### Scenario: FELIZ — Alta de recepción responde 201 sin exponer el hash

- **DADO** una sesión `admin` y un body con `email="recepcion.ficticia@cattaneo.test"`, `password` válida y `rol="recepcion"`
- **CUANDO** se hace `POST /api/usuarios-staff`
- **ENTONCES** responde `201` con `id`, `email`, `rol`, `profesional_id=null` y `activo=true`; la fila persiste `password_hash` con prefijo `$argon2id$`; y ni la respuesta ni el listado contienen `password_hash` (staff-auth, duro 10)

#### Scenario: FELIZ — Alta de odontólogo vinculada a un profesional activo

- **DADO** una sesión `admin`, un profesional activo `P1` y un body con `rol="odontologo"` y `profesional_id=P1`
- **CUANDO** se hace `POST /api/usuarios-staff`
- **ENTONCES** responde `201` y la fila persiste `rol="odontologo"` con `profesional_id=P1` (KB-03, KB-04)

#### Scenario: ERROR — Odontólogo sin profesional_id responde 400 por campo

- **DADO** una sesión `admin` y un body con `rol="odontologo"` sin `profesional_id`
- **CUANDO** se hace `POST /api/usuarios-staff`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y no se crea el usuario (KB-03, duro 1)

#### Scenario: ERROR — Recepción o admin con profesional_id responde 400 por campo

- **DADO** una sesión `admin` y un body con `rol="recepcion"` o `rol="admin"` y un `profesional_id` (casos parametrizados)
- **CUANDO** se hace `POST /api/usuarios-staff`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y no se crea el usuario (KB-03, duro 1)

#### Scenario: ERROR — Profesional inexistente o inactivo responde 400 por campo

- **DADO** una sesión `admin` y un `profesional_id` inexistente o con `activo=false` (casos parametrizados)
- **CUANDO** se hace `POST /api/usuarios-staff` con `rol="odontologo"`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y no se crea el usuario (KB-04, duro 1)

#### Scenario: ERROR — Email inválido, password corta o campo extra responden 400

- **DADO** una sesión `admin`
- **CUANDO** se hace `POST /api/usuarios-staff` con `email="sin-arroba"`, `password` de 7 caracteres o una clave extra como `telefono` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en el campo correspondiente y no se crea el usuario (duro 1)

#### Scenario: BORDE — Los umbrales de email y password aceptan sus extremos

- **DADO** una sesión `admin`
- **CUANDO** se hace `POST /api/usuarios-staff` con `password` de exactamente 8 y de 256 caracteres, y con `email` de 3 y de 320 caracteres (casos parametrizados)
- **ENTONCES** todos responden `201`, porque 8/256 y 3/320 son los bordes inclusivos de las convenciones de validación (duro 1, D-16)

### Requirement: Edición de usuario staff con invariante de rol y validación del vínculo

The system SHALL expose admin-only `PUT /api/usuarios-staff/{id}` to edit `rol`, `profesional_id` and `activo`, keeping `rol=odontologo ⇔ profesional_id`, returning 200, 400 per field or 404 for unknown ids. A non-null `profesional_id` in the patch SHALL exist and be active (422 on that field); otherwise the existing link SHALL NOT be revalidated. Edits leaving zero active admins SHALL be rejected with 422 `ultimo_admin`. (US-010, KB-04, duro 1, RN-AU-01.)

#### Scenario: FELIZ — Edición de rol y vínculo respeta el invariante

- **DADO** una sesión `admin`, un profesional activo `P2` y un usuario `recepcion`
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `rol="odontologo"` y `profesional_id=P2`
- **ENTONCES** responde `200` y la fila persiste el nuevo rol y el vínculo (KB-03, KB-04)

#### Scenario: ERROR — Dejar el invariante inconsistente responde 400

- **DADO** una sesión `admin` y un usuario `odontologo` vinculado a `P1`
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `rol="recepcion"` sin enviar `profesional_id=null`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y el usuario no cambia, porque `recepcion`/`admin` no llevan vínculo (KB-03, KB-04)

#### Scenario: ERROR — Un profesional_id inexistente o inactivo responde 422 en el campo

- **DADO** una sesión `admin` y un usuario existente
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `profesional_id` de un profesional inexistente o con `activo=false` (casos parametrizados)
- **ENTONCES** responde `422` con `detail` en `campo="profesional_id"` y el usuario no cambia, porque la referencia se valida al resolver la transición de estado (KB-04, D-6)

#### Scenario: FELIZ — Editar otros campos de un usuario vinculado a un profesional desactivado se permite

- **DADO** una sesión `admin` y un usuario `odontologo` vinculado a un profesional que fue dado de baja (`activo=false`)
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `rol="recepcion"` y `profesional_id=null`, o con `activo=false`
- **ENTONCES** responde `200` sin exigir que el profesional previo esté activo, porque el vínculo sólo se revalida cuando el patch trae `profesional_id` (KB-04, D-6)

#### Scenario: ERROR — Quitarse el rol admin siendo el único admin responde 422

- **DADO** una sesión `admin` que es el único usuario `admin` activo
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` sobre sí mismo con `rol="recepcion"`
- **ENTONCES** responde `422` con `detail.codigo="ultimo_admin"` y su fila sigue con `rol="admin"` y `activo=true`, para no dejar el sistema sin administración (RN-AU-01, D-7)

#### Scenario: ERROR — Desactivarse por PUT siendo el único admin responde 422

- **DADO** una sesión `admin` que es el único usuario `admin` activo
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` sobre sí mismo con `{"activo": false}`
- **ENTONCES** responde `422` con `detail.codigo="ultimo_admin"` y su fila sigue `activo=true`, porque `PUT activo=false` comparte la guarda de `DELETE` (RN-AU-01, D-7)

#### Scenario: FELIZ — Con otro admin activo la auto-degradación procede y corta el acceso admin

- **DADO** dos usuarios `admin` activos y una sesión de uno de ellos
- **CUANDO** ese admin se cambia a `rol="recepcion"` con `PUT /api/usuarios-staff/{id}`
- **ENTONCES** responde `200` y el siguiente request a `/api/usuarios-staff` con la misma cookie responde `403`, porque la DB es la autoridad del rol (C-03)

#### Scenario: ERROR — Email y password no son editables en v1

- **DADO** una sesión `admin` y un usuario existente
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `email` o `password` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en ese campo y el usuario no cambia, porque el email es inmutable y el reset de password queda fuera de v1 (C-03, duro 1)

#### Scenario: ERROR — PUT sin campos responde 400

- **DADO** una sesión `admin` y un usuario existente
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `{}`
- **ENTONCES** responde `400` con `detail` en `campo="body"` y el usuario no cambia (duro 1)

#### Scenario: ERROR — Usuario inexistente responde 404

- **DADO** una sesión `admin` y un UUID que no corresponde a ningún usuario staff
- **CUANDO** se hace `PUT` o `DELETE` sobre `/api/usuarios-staff/{id}` (casos parametrizados)
- **ENTONCES** responde `404` sin datos internos (staff-auth)

### Requirement: Baja lógica de usuario staff sin dejar el sistema sin admin

The system SHALL expose admin-only `DELETE /api/usuarios-staff/{id}` as a logical deactivation (`activo=false`) effective on the next request, and SHALL reject with 422 `ultimo_admin` and no changes any deactivation that would leave zero active admins. (US-010, RN-AU-01, duro 3.)

#### Scenario: FELIZ — Baja desactiva la fila y corta la sesión vigente en el siguiente request

- **DADO** una sesión `admin` y un usuario `recepcion` activo con una cookie de sesión vigente
- **CUANDO** el admin hace `DELETE /api/usuarios-staff/{id}` y luego ese usuario reusa su cookie
- **ENTONCES** la baja responde `200` con `activo=false`, la fila sigue existiendo y el request posterior del usuario desactivado responde `401`, porque la DB es la autoridad de la sesión (C-03, duro 3)

#### Scenario: ERROR — No se permite quedarse sin admin activo

- **DADO** una sesión `admin` que es el único usuario `admin` activo
- **CUANDO** se hace `DELETE /api/usuarios-staff/{id}` sobre sí mismo
- **ENTONCES** responde `422` con `detail.codigo="ultimo_admin"` y el usuario sigue `activo=true`, para no dejar el sistema sin administración (RN-AU-01)

#### Scenario: FELIZ — Con otro admin activo la baja procede

- **DADO** dos usuarios `admin` activos y una sesión `admin` de uno de ellos
- **CUANDO** se hace `DELETE` sobre el otro admin y, en una corrida separada, un admin se da de baja a sí mismo mientras el otro sigue activo
- **ENTONCES** ambas operaciones responden `200` y la fila destinataria queda `activo=false`, porque en cada caso queda al menos un admin activo (RN-AU-01, D-7)

#### Scenario: BORDE — Dos admins dados de baja en simultáneo dejan uno activo

- **DADO** dos usuarios `admin` activos con sesiones vigentes
- **CUANDO** ambos se dan de baja mutuamente en transacciones concurrentes
- **ENTONCES** una operación responde `200` y la otra `422 ultimo_admin`, y siempre queda al menos un admin activo, porque la guarda bloquea y cuenta los admins activos dentro de la transacción (RN-AU-01, duro 2)

#### Scenario: BORDE — Carreras mixtas PUT y DELETE también dejan un admin activo

- **DADO** dos usuarios `admin` activos con sesiones vigentes
- **CUANDO** se ejecutan en simultáneo `PUT {"activo": false}` sobre uno y `DELETE` sobre el otro, y en otra corrida dos `PUT {"activo": false}` mutuos (casos parametrizados)
- **ENTONCES** siempre queda exactamente un admin activo: la primera operación responde `200` y la segunda `422 ultimo_admin`, porque ambas toman el mismo lock ordenado sobre las filas admin (RN-AU-01, duro 2, D-7)

#### Scenario: BORDE — Repetir la baja es idempotente

- **DADO** un usuario staff con `activo=false` y una sesión `admin`
- **CUANDO** se repite `DELETE /api/usuarios-staff/{id}`
- **ENTONCES** responde `200` con `activo=false` y no se altera ningún otro dato (duro 3)

### Requirement: Unicidad de email y reactivación de usuarios staff

The system SHALL enforce unique staff email across active and inactive rows (409 on duplicates) and SHALL allow reusing an email only by reactivating that row with `PUT /api/usuarios-staff/{id}` y `{"activo": true}`. (US-010, KB-04.)

#### Scenario: ERROR — Alta con email ya usado responde 409

- **DADO** una sesión `admin` y un usuario existente con `email="recepcion.ficticia@cattaneo.test"`
- **CUANDO** se hace `POST /api/usuarios-staff` con el mismo email o con otra capitalización (casos parametrizados)
- **ENTONCES** responde `409` con `detail.codigo="email_duplicado"` y no se crea un segundo usuario, porque `usuario_staff.email` es `CITEXT UNIQUE` (KB-04)

#### Scenario: ERROR — El email de un usuario inactivo también está tomado

- **DADO** un usuario con `activo=false` y una sesión `admin`
- **CUANDO** se hace `POST /api/usuarios-staff` con su email
- **ENTONCES** responde `409` con `detail.codigo="email_duplicado"` y el mensaje indica que debe reactivarse la fila existente (duro 3)

#### Scenario: FELIZ — Reactivar habilita el login con la password existente

- **DADO** un usuario `odontologo` con `activo=false` y una sesión `admin`
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `{"activo": true}` y luego el usuario hace `POST /api/auth/login` con su password previa
- **ENTONCES** la reactivación responde `200` y el login responde `200` con cookie de sesión, sin crear otra fila (US-010)

#### Scenario: BORDE — Reactivar un usuario ya activo es un 200 sin efectos

- **DADO** un usuario activo y una sesión `admin`
- **CUANDO** se hace `PUT /api/usuarios-staff/{id}` con `{"activo": true}`
- **ENTONCES** responde `200` y la fila no cambia (duro 3)

### Requirement: Listado admin de usuarios staff y acceso exclusivo

The system SHALL expose admin-only `GET /api/usuarios-staff` listing every staff user with keyset pagination, explicit columns and no `password_hash`, and SHALL require an `admin` session on all staff-user endpoints (401 without session, 403 otherwise; those RBAC scenarios live in the main `staff-auth` spec and are not duplicated here). (RN-AU-01, duro 1/7.)

#### Scenario: FELIZ — El listado incluye activos e inactivos sin hash

- **DADO** un usuario activo, otro inactivo y una sesión `admin`
- **CUANDO** se hace `GET /api/usuarios-staff?limit=20`
- **ENTONCES** responde `200` con ambos usuarios en `items`, cada uno con `id`, `email`, `rol`, `profesional_id` y `activo`, y `next_cursor`; ningún item contiene `password_hash` (duro 7)

#### Scenario: FELIZ — El listado pagina por keyset con next_cursor

- **DADO** tres usuarios staff y una sesión `admin`
- **CUANDO** se pide `GET /api/usuarios-staff?limit=2` y luego el `next_cursor`
- **ENTONCES** la primera respuesta trae dos items con `next_cursor` no nulo, la segunda el restante con `next_cursor=null`, y las dos páginas no repiten ni omiten usuarios (duro 7)

#### Scenario: ERROR — Cursor inválido o límite fuera de rango responde 400

- **DADO** una sesión `admin`
- **CUANDO** se pide `GET /api/usuarios-staff?cursor="no-es-uuid"` o `limit=0` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en el campo inválido (duro 1)

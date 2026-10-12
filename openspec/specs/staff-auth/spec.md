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

# Proposal — c-03-auth-staff-rbac

## Why

Ningún endpoint staff puede existir sin una frontera de confianza verificable: hoy `UsuarioStaff` persiste (C-02) pero no hay login, sesión ni autorización, por lo que cualquier escritura staff de C-04 (disponibilidades/bloqueos) o C-07 (CRUD recepción) nacería sin control de acceso. Este change cierra esa frontera antes de esos writes: establece quién es staff (login/logout con sesión), qué puede hacer cada rol (RBAC recepción/odontólogo/admin) y con qué garantías (hash final, cookie segura, sin enumeración, rate-limit).

## What Changes

- `POST /api/auth/login` (email+password) → sesión en cookie httpOnly con rol; `POST /api/auth/logout` invalida la sesión.
- Dependencia `require_role(...)` por router + scoping de odontólogo a su `profesional_id`; herencia Admin ⊇ Recepción ⊇ lectura, odontólogo fuera de la cadena de recepción.
- Decisión final de hash (bcrypt vs argon2) + rotación al primer login + migración del hash semilla PBKDF2 transitorio de C-02.
- Schemas Pydantic estrictos de login (`extra='forbid'`); errores genéricos indistinguibles (usuario inexistente ≡ password incorrecta ≡ cuenta inactiva); rate-limit en login.
- Tests: login/logout, matriz RBAC (KB-03), aislamiento odontólogo, sin token → 401/403.

## Capabilities

### New Capabilities

- `staff-auth`: autenticación staff por sesión (login/logout, hash + rotación, cookie httpOnly, rate-limit, no-enumeración) y autorización por rol (`require_role`, herencia Admin ⊇ Recepción, scoping odontólogo a `profesional_id`, semántica 401 vs 403).

### Modified Capabilities

- Ninguna. `turno-lifecycle` y `paciente-privacidad` (C-02) se leen como convenciones adyacentes (token por turno, genéricos 403) pero ningún requirement suyo cambia.

## Impact

- Nuevo: `backend/app/modules/auth/*` (router `/api/auth/*`, schemas, service, dependencia `require_role`), `backend/app/core/security.py` (hash/verify + sesión), posible migración Alembic `002` (solo si la decisión de hash/rotación exige columnas, p. ej. marcador de rotación — propiedad de ESTE change, no de C-04).
- Afectado: `backend/app/db/seed.py` (hash semilla migra a esquema final), `backend/app/main.py` (ya registra `auth_router` stub — sin cambio de patrón).
- No tocado: routers/endpoints de C-04 (`/api/profesionales/*`, `/api/disponibilidades`, `/api/bloqueos`, cómputo de slots) — solo lectura compartida de modelos C-02 con el agente sibling.
- Dependencias: C-02 ✅. Desbloquea C-07/C-10/C-11 (todo write staff).

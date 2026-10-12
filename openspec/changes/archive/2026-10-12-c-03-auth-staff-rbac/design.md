# Design — c-03-auth-staff-rbac

## Context

See `proposal.md` (Why) for motivation. Current state (verified on disk): `backend/app/models/usuario_staff.py` (`email CITEXT UNIQUE`, `password_hash TEXT`, `rol` enum recepcion/odontologo/admin, `profesional_id FK NULL`, `activo BOOL`) + migration `001_core_models` applied; `backend/app/db/seed.py` hashes the admin seed with TRANSITORY stdlib PBKDF2-HMAC-SHA256 (`pbkdf2_sha256$…`, 600k iters) with an explicit handoff: C-03 owns the final scheme + first-login rotation. `backend/app/modules/auth/router.py` is an empty stub (`APIRouter(prefix="/api/auth")`) already registered in `main.py` — no registration change needed. `backend/app/core/` contains ONLY `config.py`: the C-01 "rate-limit base" never materialized, so this change owns its login throttling (no shared limiter to reuse). `Settings` has `SECRET_KEY` (JWT signing) and `ADMIN_EMAIL/PASSWORD`; no new env vars planned. Tests run on real PG via `db_session`/`TestClient` fixtures (`conftest.py`); no DB needed to propose, PG required at apply.

## Goals / Non-Goals

**Goals:**

- Close the staff trust boundary before any staff write exists (C-04/C-07 consume `require_role`, never re-implement it).
- Lock every governance-CRÍTICO behavior as spec ACs: final hash + rotation, cookie flags + lifetime, generic errors, 401-vs-403, throttle-without-lockout.
- Zero schema change if possible (rotation detectable by hash prefix; avoids an Alembic `002` and any coordination with sibling C-04).

**Non-Goals:**

- No user/role management endpoints (CRUD usuarios-staff = C-11); no password-change/reset flow (post-v1); no patient auth (token-per-turno only, C-05/C-06).
- No `profesionales/disponibilidad` design (sibling C-04 owns it; shared read-only access to C-02 models).
- No frontend login UI (C-10); this change ships the API contract + cookie it will consume.

## Decisions

### D-1 — Final hash: argon2id (argon2-cffi), PBKDF2 verify-only during transition

New hashes use argon2id (`$argon2id$…`, OWASP first choice: memory-hard, no 72-byte truncation like bcrypt). `verify` sniffs the prefix: `$argon2id$` → argon2 verify; `pbkdf2_sha256$` → legacy stdlib verify (code moved from `seed.py`, kept verify-only). On a successful login with a legacy hash, re-hash to argon2id and persist (first-login rotation, transparent, password unchanged). New dependency `argon2-cffi` (pure wheel, single-host friendly).

- *Alternative*: bcrypt. Rejected: 72-byte password truncation is a silent footgun with no compensating advantage at this scale; argon2id dominates on both security guidance and correctness.
- *Alternative*: keep PBKDF2 as final. Rejected: it was declared TRANSITORY in the C-02 handoff to avoid adding a dependency prematurely — that condition now ends.
- *Applies*: backend-development (argon2id/bcrypt hashes, OWASP pass), C-02 handoff closure.

### D-2 — Session: stateless signed JWT (HS256, SECRET_KEY) in httpOnly cookie

`POST /api/auth/login` → JWT `{sub, rol, profesional_id, exp}` signed HS256 with `SECRET_KEY`, set as cookie `session` httpOnly, `SameSite=Lax`, `Secure=true` in prod (TLS from PaaS), `Path=/`, lifetime = full workday (12h, covers Flujo 5 jornada + cierre). Stateless: no session table, no migration, single-process safe. `POST /api/auth/logout` clears the cookie (`Max-Age=0`). Every staff request re-loads `UsuarioStaff` by `sub` (fresh `activo/rol/profesional_id`; JWT claims are hints, DB is authority — deactivation takes effect on next request despite statelessness).

- *Alternative*: opaque server-side sessions in PG. Rejected: needs a session table + `002` migration + cleanup job for zero v1 benefit (revocation beyond deactivation/role-change is not a v1 requirement).
- *Alternative*: JWT in `Authorization` header. Rejected: KB fixes httpOnly cookie (XSS-safe storage); header tokens invite localStorage.
- *Applies*: backend-development (session/JWT in httpOnly cookie, SameSite/Secure per KB-08).

### D-3 — `require_role(...)` dependency + odontólogo scoping helper

`backend/app/modules/auth/deps.py`: `require_role(*roles)` — missing/invalid/expired cookie → 401 generic; valid session with `activo=false` → 401 generic (indistinguishable); role not in `*roles` → 403 generic. Role check is hierarchical at call sites (`admin` passes any `require_role`; recepción passes lectura+escritura but not admin-only). `require_own_profesional()` for odontólogo routes: compares path/query `profesional_id` against DB-loaded `profesional_id`; mismatch or NULL link → 403, no data leaked. Patient token paths (`?token=`) never touch this dependency (separate C-05/C-06 concern).

- *Alternative*: middleware global with path allowlist. Rejected: per-router `Depends` is the KB-08 contract and keeps public/staff boundaries explicit at each router (C-04/C-07 just add the dependency).
- *Applies*: KB-03 matrix, RN-AU-01, backend-development (RBAC via dependencies).

### D-4 — Login throttling in-process (no lockout), generic 429

C-01 left no limiter, so: in-process sliding-window counter per IP on `POST /api/auth/login` (limit + window fixed here, e.g. 10 intentos/min/IP — small enough to blunt credential stuffing, large enough for a real reception desk behind NAT). Excess → 429 with identical message regardless of credential validity. NO permanent account lockout in v1 (lockout = self-inflicted denial of service for a 3-person desk + support burden; throttling is the control). Unknown-email path runs a dummy argon2 verify so timing does not enumerate users.

- *Alternative*: slowapi/Redis-backed limiter. Rejected: Redis is only documented (`REDIS_URL` optional, PB-03); slowapi adds a dependency for one endpoint — the in-process window matches the APScheduler-era single-process topology and migrates with it.
- *Alternative*: lockout after N failures. Rejected: see above; explicitly recorded as deferred (revisit only with abuse evidence).
- *Applies*: RN-AU-03 (spirit: anti-abuse on sensitive endpoints), backend-development (rate-limit login, generic errors).

### D-5 — No Alembic migration in this change (prefix-sniffed rotation)

`password_hash TEXT` already stores any format; rotation state = "hash starts with `$argon2id$`". No new columns, no `002`, no coordination with sibling C-04. `seed.py` switches to the final hasher for new seeds; legacy `verify_password` stays as verify-only path. If apply discovers a real need (e.g. forced-rotation flag), it owns `002` in ITS tasks.

- *Applies*: supabase-postgres-best-practices (no gratuitous schema change; connection discipline only).

### D-6 — Strict login schemas, 401-vs-403, no enumeration end-to-end

`LoginIn {email, password}` + `extra='forbid'` (rule 1, no D-2 exception — that was Settings-only). 400 per-field on shape errors; 401 generic on ANY credential failure (unknown ≡ wrong ≡ inactive); 403 only for authenticated-but-unauthorized. Login response body carries `{rol, email}` convenience fields (no hash, no token in body — cookie is the credential).

### D-7 — Logout invalidation via in-process `jti` denylist (accepted at human review, apply-time addition)

**What**: `backend/app/core/security.py` keeps an in-process denylist `_revoked: dict[jti, exp_ts]`; `POST /api/auth/logout` decodes the cookie and calls `revoke_session(jti, exp)`; every request through `get_current_staff` (`backend/app/modules/auth/deps.py:46`) calls `is_session_revoked(claims["jti"])` after signature/`exp` validation and raises generic 401 on hit. Pruning is lazy: `_prune(now)` runs on every `revoke_session`/`is_session_revoked` call and drops entries with `exp <= now`, so the set stays bounded by live sessions.

**Why**: pure stateless JWT (D-2 as designed) leaves a logged-out cookie reusable until `exp`, violating the spec AC `staff-auth/Logout-invalida` (logout-then-reuse MUST be 401). The denylist fixes it with zero schema change and zero new dependency, consistent with the single-process v1 topology (same rationale as D-4 throttling). Server-side session table explicitly rejected (D-2 alternative stands): `002` migration + cleanup job for no v1 benefit.

**Concurrent-device independence preserved**: each login mints a fresh `jti` (`uuid4`, `create_session_token`), so logout revokes only that device's `jti`; the other device's session stays valid (spec EDGE scenario covered by test).

- *Applies*: spec `staff-auth/Logout-invalida`, 170 pytest PG-backed green, `ruff` clean.

## Risks / Trade-offs

- [Riesgo] Stateless JWT logout is client-side clear (a stolen cookie lives until `exp`) → Mitigación: 12h lifetime bounds exposure; deactivation/role change enforced per-request via DB lookup; theft response = rotate `SECRET_KEY` (invalidates all) + documentado en tasks.
- [Riesgo] In-process throttle resets on deploy and is per-process → Mitigación: aceptado en topología single-process v1; el límite es anti-abuso, no contable; si el worker escala a multi-proceso, migrar a Redis con el resto (PB-03).
- [Riesgo] `SameSite=Lax` si C-12 sirve front y API en orígenes distintos → Mitigación: flags documentados como configurables (`SameSite=None; Secure` en ese caso); pregunta abierta ABAJO para C-12, specs ya exigen "según lo fijado en design".
- [Riesgo] Sibling C-04 toca los mismos modelos en lectura → Mitigación: contrato de solo-lectura compartida; este change no añade columnas, así que ningún diff de migración puede colisionar.
- [Trade-off] Sin lockout, un atacante persistente puede reintentar indefinidamente a ritmo limitado → aceptado: 10/min/IP hace el stuffing inviable contra passwords no triviales; el admin seed exige rotación al primer login (password temporal corta vida).

## Migration Plan

1. Merge: solo añade archivos (`modules/auth/{schemas,service,deps}.py`, `core/security.py`, `core/ratelimit.py`, tests); `seed.py` cambia de hasher (hashes nuevos argon2id; verify dual). Sin migración (D-5). Sin datos previos que migrar (admins seed existentes rotan solos al primer login).
2. Deploy: instalar `argon2-cffi`; `SECRET_KEY` ya exigido por Settings (fail-fast C-01). Rollback: revertir el merge; hashes argon2id ya rotados siguen verificables tras rollback SOLO si el rollback conserva el verify dual — anotado en tasks como guardia.
3. Verificación: `pytest` PG-backed verde (matriz RBAC parametrizada, rotación, 401/403, 429) + `ruff check` + `openspec validate --change c-03-auth-staff-rbac`.

## Open Questions

- Cookie vs JWT quedó cerrado aquí (JWT-en-cookie httpOnly, D-2); lo que C-12 debe confirmar es el par SameSite/Secure final según la topología de orígenes del deploy (Lax por defecto, None+Secure si front/API se separan) — no cambia specs ni tasks.
- Lifetime 12h: ¿cubre la jornada real del consultorio o se prefiere 8h + re-login al cierre? No cambia el diseño (una constante); se fija en apply con dato operativo.
- ¿`GET /api/auth/me` (rol/profesional para la UI staff de C-10) entra en este change o en C-10? RESUELTO en apply: **entra en C-03** (`GET /api/auth/me` → `200 {email, rol, profesional_id}`, 401 sin sesión; `MeOut` en `schemas.py`). La propuesta de fallback a C-10 queda descartada — C-10 consume este endpoint.

## Archive Note (2026-10-12 — apply verified, human review: "continuar")

- **Apply verificado**: 170 pytest en PG real verdes, `ruff` limpio, sin migración (head sigue `001_core_models`), `openspec validate` válido (7/7 specs incl. `staff-auth` nuevo).
- **Diferidos cerrados**: (a) par SameSite/Secure final → **C-12** (implementado: `samesite="lax"`, `secure` derivado de `FRONTEND_URL.startswith("https")`, sin nueva env var); (b) lifetime 12h = constante `SESSION_LIFETIME_H` en `app/core/security.py:27`, ajustable sin cambiar diseño; (c) `GET /api/auth/me` queda en C-03 (ver arriba).
- **Handoff a C-04** (importar, NO duplicar — opción A aprobada):
  - `from app.modules.auth.deps import get_current_staff, require_role, require_own_profesional` (+ alias `CurrentStaff` para firmas de ruta).
  - `from app.core.ratelimit import check_rate_limit` (throttle de login; C-04 no necesita reimplementar límite).
  - Comportamientos bloqueados que C-04 consume tal cual: argon2id + rotación al primer login (D-1/D-5); JWT HS256 en cookie `session` httpOnly + denylist `jti` con chequeo por-request en `get_current_staff` (D-2/D-7); matriz RBAC Admin ⊇ Recepción ⊇ lectura + scoping odontólogo propio (D-3); 401-vs-403 genéricos sin enumeración (D-6); throttle 10/min/IP con 429 genérico sin lockout (D-4).
  - C-04 solo añade `Depends(require_role(...))` / `require_own_profesional(...)` en sus routers; ningún cambio de contrato de auth previsto.

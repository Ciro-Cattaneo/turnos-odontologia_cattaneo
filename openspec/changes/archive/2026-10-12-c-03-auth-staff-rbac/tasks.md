# Tasks — c-03-auth-staff-rbac

> Nota apply: los tests DB-backed exigen PG 16 alcanzable con migración `001` (fixtures `db_session`/TestClient de `conftest.py`, datos ficticios `.test`); este host no tiene PG local (handoff C-02) — resolver antes de las tareas con capa `db/api`. Proponer no requirió DB. TDD red-green-refactor en toda tarea con test; sin mocks del verificador de hash (test-guard: verificar real contra vectores conocidos). Sin commits (regla 11).

## 1. Hash final argon2id + rotación (D-1, D-5)

- [x] 1.1 `argon2-cffi` + `backend/app/core/security.py` (hash argon2id, verify dual por prefijo, rotación) con TDD — test: `backend/tests/test_auth_hash.py` (capa: unit/service, sin DB: vectores argon2 conocidos verifican True, legacy `pbkdf2_sha256$` verifica True, password incorrecta y formato corrupto → False, nunca plaintext) — verificar: `pytest backend/tests/test_auth_hash.py` verde + `ruff check` limpio — ACs: `staff-auth/Hash-final-con-rotación` (happy + rotated-hash login).
- [x] 1.2 `seed.py` al hasher final (hashes nuevos `$argon2id$`, verify legacy solo-lectura) con TDD — test: `backend/tests/test_seed_admin.py` (capa: db, PG real: seed crea admin con hash `$argon2id$`, doble corrida sigue idempotente a 1 admin, legacy semilla sigue verificando) — verificar: `pytest backend/tests/test_seed_admin.py` verde — ACs: `staff-auth/Hash-final-con-rotación` + `core-models/Seed-admin-idempotente` (sin regresión).

## 2. Login / logout por cookie (D-2, D-6)

- [x] 2.1 Schemas estrictos `LoginIn {email, password}` (`extra='forbid'`) con TDD — test: `backend/tests/test_auth_schemas.py` (capa: schemas/unit, sin DB: campo extra → error, email malformado / password faltante → error por campo) — verificar: `pytest` verde — ACs: `staff-auth/Schemas-estrictos` (400 por campo).
- [x] 2.2 `POST /api/auth/login` (JWT HS256 en cookie httpOnly + 401 genérico + dummy-verify) con TDD — test: `backend/tests/test_auth_login.py` (capa: api, PG real + TestClient: credenciales válidas → 200 + cookie httpOnly/SameSite/Secure + lifetime; válida/wrong ≡ desconocido ≡ inactivo → 401 idéntico cuerpo y status; hash rotado verifica directo; dos dispositivos → sesiones independientes) — verificar: `pytest backend/tests/test_auth_login.py` verde — ACs: `staff-auth/Login-sesión`, `staff-auth/Errores-genéricos`, `staff-auth/Cookie-flags`, `staff-auth/Hash-final-con-rotación`.
- [x] 2.3 `POST /api/auth/logout` (limpia cookie, reuse → 401, no-op sin sesión) con TDD — test: `backend/tests/test_auth_login.py` (misma capa/api: logout → 200 + cookie expirada; reuse → 401; sin cookie → 200 sin error) — verificar: `pytest` verde — ACs: `staff-auth/Logout-invalida`.
- [x] 2.4 `GET /api/auth/me` mínimo (`{email, rol, profesional_id}`, 401 sin sesión) con TDD — test: `backend/tests/test_auth_login.py` (capa: api: con sesión → 200; sin sesión → 401; refleja rol actualizado desde DB) — verificar: `pytest` verde — ACs: soporte a C-10 (si apply lo rechaza, cae a C-10 sin tocar specs).

## 3. require_role + scoping odontólogo (D-3)

- [x] 3.1 `backend/app/modules/auth/deps.py` (`require_role(*roles)` jerárquico + `require_own_profesional()`, 401-vs-403) con TDD — test: `backend/tests/test_auth_rbac.py` (capa: api, PG real, parametrizado rol × recurso: admin→todo 200, recepción→lectura/escritura 200 + admin-only 403, odontólogo→propia 200 + P2 403 + sin link 403, sin cookie → 401 en todo) — verificar: `pytest backend/tests/test_auth_rbac.py` verde — ACs: `staff-auth/require_role-herencia`, `staff-auth/Odontólogo-scoping`, `staff-auth/401-vs-403`.
- [x] 3.2 Cablear `require_role` en routers staff existentes como prueba de consumo (solo los que ya existen como stub, sin diseñar C-04) con TDD — test: extensión de `test_auth_rbac.py` (capa: api: stub protegido responde 401/403 según matriz) — verificar: `pytest` verde — ACs: `staff-auth/require_role-herencia` (el contrato que C-04/C-07 reutilizan).

## 4. Rate-limit login sin lockout (D-4)

- [x] 4.1 `backend/app/core/ratelimit.py` (ventana deslizante in-process por IP) + cableado solo en login con TDD — test: `backend/tests/test_auth_ratelimit.py` (capa: api, PG real: ráfaga sobre el límite → 429; 429 idéntico con credenciales válidas e inválidas; tras la ventana, login válido → 200, sin bloqueo permanente) — verificar: `pytest backend/tests/test_auth_ratelimit.py` verde — ACs: `staff-auth/Rate-limit-sin-lockout` (happy + business-error).

## 5. Integración y cierre

- [x] 5.1 Rotación E2E de semilla legacy (admin PBKDF2 → primer login → hash `$argon2id$` persistido, segundo login directo) con TDD — test: `backend/tests/test_auth_rotation.py` (capa: api+db, PG real: inserta admin con hash `pbkdf2_sha256$` ficticio, login 200, re-lee `password_hash` con prefijo nuevo, segundo login 200) — verificar: `pytest` verde — ACs: `staff-auth/Hash-final-con-rotación` (cierra el handoff C-02).
- [x] 5.2 Guardia de rollback (hashes argon2id verificables si se revierte el merge conservando verify dual) + suite completa — test: re-ejecutar `pytest backend/tests/` entero + `ruff check backend/` + `openspec validate --change c-03-auth-staff-rbac` — verificar: todo verde, sin regresión en specs C-02 (`turno-lifecycle`, `paciente-privacidad`) — ACs: transversales.

## Workflow follow-up

- Ejecutar `/opsx:apply c-03-auth-staff-rbac` (requiere PG 16 alcanzable) y luego archivar + marcar `[x]` C-03 en CHANGES.md.
- Avisar al agente sibling (C-04): `require_role` disponible para sus writes; sin cambios de schema que coordinar.


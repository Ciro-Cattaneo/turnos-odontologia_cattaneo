# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Writing, reviewing, or refactoring React/Next.js code; React components, Next.js pages, data fetching, bundle optimization, performance improvements | vercel-react-best-practices | C:\Users\ciroc\.agents\skills\vercel-react-best-practices\SKILL.md |
| Writing or changing anything in Postgres: tables/columns, schema design, migrations, RLS policies, indexes, triggers, functions, queues/scheduled jobs, pgvector, diagnosing slow queries, CPU, timeouts, EXPLAIN, connections, locking, bloat | supabase-postgres-best-practices | C:\Users\ciroc\.agents\skills\supabase-postgres-best-practices\SKILL.md |
| Set up Prisma Postgres, connect app to Prisma Postgres, Prisma Postgres setup in v0/Vercel Marketplace | prisma-postgres-setup | C:\Users\ciroc\.agents\skills\prisma-postgres-setup\SKILL.md |
| SQL query tuning, indexing strategies, execution plan analysis, pagination, batch operations, performance monitoring (MySQL, PostgreSQL, SQL Server, Oracle) | sql-optimization | C:\Users\ciroc\.agents\skills\sql-optimization\SKILL.md |
| Designing APIs, implementing authentication, optimizing DB queries, CI/CD, security vulnerabilities, microservices, production-ready backend systems (Node/Python/Go/Rust, FastAPI, Postgres, REST/GraphQL/gRPC, OAuth/JWT) | backend-development | C:\Users\ciroc\.agents\skills\backend-development\SKILL.md |
| Reviewing generated/changed test code before ship/commit/merge; write/add/review tests; PR diffs containing tests (pytest, PHPUnit/Pest, Jest/Vitest, Go) | test-guard | C:\Users\ciroc\.agents\skills\test-guard\SKILL.md |
| Write tests, improve coverage, practice TDD, generate mocks/stubs, red-green-refactor (Jest, Pytest, JUnit, Vitest, Mocha) | tdd-guide | C:\Users\ciroc\.agents\skills\tdd-guide\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### vercel-react-best-practices
- Eliminate waterfalls: parallelize independent fetches with Promise.all, start promises early / await late, defer await into branches where used
- Bundle: import directly (no barrel files), prefer statically analyzable paths, next/dynamic for heavy components, load third-party (analytics/logging) after hydration
- Client fetching: use SWR for dedup; dedupe global event listeners; passive listeners for scroll; version + minimize localStorage data
- Re-renders: never define components inside components; derive state during render (not effects); use startTransition/useDeferredValue for non-urgent work; functional setState for stable callbacks
- Lists/media: content-visibility for long lists; animate div wrapper not SVG; hoist static JSX out of components; reduce SVG coordinate precision
- Gotcha: check rule file in `rules/` before applying an unfamiliar prefix (`async-*`, `bundle-*`, `server-*`, `client-*`, `rerender-*`, `rendering-*`)

### supabase-postgres-best-practices
- Load BEFORE any Postgres change, even one column or one query — schema, migration, security, and SQL authoring all need these rules
- Query: create indexes for filter/join/order columns; prefer composite indexes in filter order; partial indexes for `WHERE estado='...'` patterns; covering indexes for hot reads
- Schema: lowercase identifiers; explicit PKs; FK columns need their own index; right-sized types (timestamptz, uuid, enums); CHECK constraints to help the planner
- Concurrency: keep transactions short; SELECT FOR UPDATE / advisory locks for slot-style contention; SKIP LOCKED for worker dequeue; EXCLUDE USING gist for no-overlap ranges
- Connections: pool (transaction mode); prepared statements; watch idle timeouts and connection limits on single-instance
- Security: RLS policies must be performant (indexed, non-volatile checks); least-privilege grants; never expose rows to wrong tenant/user
- Diagnose with EXPLAIN ANALYZE + pg_stat_statements; VACUUM/ANALYZE after bulk loads

### prisma-postgres-setup
- Reuse existing DB/connection when present — verify project, database, and env before provisioning anything new
- Honor explicit ORM/driver choice (Drizzle, pg, DB-only); do not restart setup for routine query/schema work in an already-configured app
- Connection string goes in secret env config only, never source code or chat; preserve unrelated env entries; ensure local secret files are git-ignored
- App processes vs CLI may load different env files — load the intended file for that command; missing var in shell ≠ missing DB
- Hand ORM version/config to version-matched ORM guidance; verify with a read-only query through the app's ORM/driver and report without secrets
- If provisioning blocked by permissions/quota: report blocker, never delete another resource or switch workspaces to work around it
- NOTE for this project: stack uses SQLAlchemy 2.x + Alembic (not Prisma ORM) — apply only the connection/env/provisioning discipline, not Prisma codegen

### sql-optimization
- Never SELECT * in production — list explicit columns
- Never wrap indexed columns in functions in WHERE (e.g. YEAR(created_at)) — use sargable ranges (>= / <)
- Prefer JOIN over IN-subquery; window functions over correlated subqueries; EXISTS over IN where appropriate
- Composite index column order must match filter order; partial indexes for status-filtered queries; avoid over-indexing (hurts INSERT/UPDATE)
- Pagination: cursor/keyset (WHERE id/created_at + LIMIT), never large OFFSET
- Batch inserts in one statement; single conditional-aggregation query instead of N count queries; temp tables for complex multi-step ops
- OR across different columns → UNION ALL when planner stalls; INNER vs LEFT chosen deliberately, filter early in WHERE/JOIN ON
- Verify with EXPLAIN + realistic data volumes; monitor slow queries continuously

### backend-development
- FastAPI: Pydantic-strict input validation on every endpoint; parameterized queries only (no string-built SQL); consistent error shape with generic messages on auth (no user enumeration)
- Auth: Argon2id/bcrypt hashes; OAuth 2.1 + PKCE where external; JWT/session in httpOnly cookie; RBAC via dependencies (require_role); rate-limit public + login endpoints
- API: explicit status codes (400 field errors, 409 conflicts + alternatives, 422 state violations, 401/403 auth); OpenAPI auto-docs; versioned, paginated listings
- Perf: index hot paths; connection pooling; cache reads (Redis only if volume justifies — default single-process here); CDN for static
- Testing: 70-20-10 pyramid (unit-integration-E2E); contract tests at service boundaries; migration tests (most migrations fail without them)
- Deploy: Docker + CI/CD + health checks; blue-green/canary or feature flags; structured logging + Prometheus/Grafana/OpenTelemetry
- Security baseline: OWASP Top 10 pass on every change (injection, broken access control, auth failures, SSRF, misconfig)

### test-guard
- Test behavior, not implementation — assert return values/observable side effects, never that an internal helper was called
- Every mock must be justified — mock only at system boundaries (network/HTTP, LLM APIs, DB, external FS files, clock/randomness, third-party SDKs); never mock internal helpers or state/DTOs (construct real instances)
- One scenario per test; merge same-setup value-variants into one data-driven test (parametrize / test.each / DataProvider)
- Every test must justify its existence: "what bug does this catch that no other test catches?" — delete typo/constant/framework-guarantee tests
- Name tests `test_<scenario>_<expected_outcome>` reading like a requirement
- Production regression tests are sacred — reference incident, never delete (exempt from justification rule)
- DB/persistence under test → real test DB with real migrations via fixtures; mock DB only when persistence is a side effect

### tdd-guide
- Red-green-refactor always: failing test first (RED), minimal code to pass (GREEN), refactor with tests green; one AC criterion → at least one test
- Backend tests: pytest + parametrize for variants; shared fixtures in conftest.py (db_session with rollback); real Pydantic instances, no mocked DTOs
- Frontend tests: Vitest (preferred over Jest, ~50% faster); test.each for variants; MSW for HTTP boundaries; snapshot discipline (assert behavior, not markup dumps)
- Coverage: analyze LCOV/JSON/XML, fix P0 (uncovered error paths) first; threshold typically 80%+; 100% line coverage ≠ good tests
- Mutation-test critical paths (auth, turnos overlap, cancel rules): target 85%+ mutation score; mutants surviving on `<` vs `<=` signal off-by-one gaps
- Stop-and-ask: ambiguous AC, unknown boundary values, >50 tests, undocumented third-party behavior, security-sensitive flows (auth/payments) need sign-off
- Traceability: number ACs in spec, reference number in test docstring (e.g. `# AC-3: ...`)

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| (none yet) | — | No AGENTS.md / CLAUDE.md / .cursorrules / GEMINI.md / copilot-instructions.md in project root. Project conventions section starts empty — CLAUDE.md/AGENTS.md are generated in the next phase (agent-instruction). Re-run registry afterwards to index them. |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.

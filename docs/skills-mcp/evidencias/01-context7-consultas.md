# Evidencia — consultas a Context7 para C-05

Fecha: 2026-11-02. Change: `c-05-reserva-online-backend`. Uso real del MCP `context7` (`resolve-library-id` + `query-docs`). Solo datos ficticios; no se enviaron datos de pacientes ni secretos.

## Consulta 1 — SQLAlchemy 2.0: `IntegrityError` + `begin_nested()` (SAVEPOINT)

- Librería resuelta: `/sqlalchemy/sqlalchemy` (SQLAlchemy, fuente High; versiones `rel_2_0_55` / `rel_2_1_6`).
- Consulta exacta: “How to handle IntegrityError inside a transaction and use begin_nested SAVEPOINT to continue querying after a constraint violation”.
- Resumen de la respuesta (3-6 líneas): `Session.begin_nested()` emite `BEGIN SAVEPOINT` dentro de la transacción vigente; al salir bien hace `RELEASE SAVEPOINT` y, ante excepción, `ROLLBACK TO SAVEPOINT`, dejando viva la transacción exterior. En PostgreSQL un `IntegrityError` normalmente aborta toda la transacción, pero capturado dentro de `begin_nested()` solo revierte el savepoint. El patrón recomendado es `try: with session.begin_nested(): ... except IntegrityError: ...` y luego continuar operando en la transacción exterior. Al entrar al savepoint se hace flush incondicional del estado pendiente.
- Decisión que confirmó/cambió: confirma **D-2**. El `INSERT` del `Turno` se envuelve en `begin_nested()`; si salta `no_solape_prof`, se revierte solo ese savepoint y se pueden consultar los alternativos del mismo día antes de responder 409. Sin savepoint, el `IntegrityError` dejaría la transacción abortada y la consulta de alternativos fallaría.

## Consulta 2 — Pydantic v2: `extra='forbid'`, `loc` y validador de email

- Librería resuelta: `/websites/pydantic_dev_validation` (Pydantic, fuente High; docs v2.12).
- Consulta exacta: “Pydantic v2 extra forbid nested model validation error loc and custom field validator for email error shape”.
- Resumen de la respuesta (3-6 líneas): `ConfigDict(extra='forbid')` genera un error `type=extra_forbidden` con `loc` apuntando al campo extra. En modelos anidados, `loc` es una ruta por niveles (ej. `('items', 1, 'value')`), y `ValidationError.errors()` expone `type`, `loc`, `msg` e `input`. Un validador de campo que lanza `ValueError` se reporta con el `loc` del campo validado. El primer elemento de `loc` identifica el campo; los siguientes describen la ruta anidada.
- Decisión que confirmó/cambió: confirma **D-4**. El error de mail inválido se emite con `campo: "paciente.email"` (un único elemento en `detail`), y los extras se reportan en su campo (`paciente.foo` o `body.foo`). Se usa un validador/patrón propio y **no** `EmailStr`, porque el TLD reservado `.test` que exige la regla dura 12 es rechazado por el validador RFC (precedente: `LoginIn` de C-03). El router normaliza el `loc` de FastAPI quitando el prefijo `body` para que el contrato sea estable.

## Pendientes

Ninguno: ambas consultas respondieron correctamente. No se requirió reintento ni API key.

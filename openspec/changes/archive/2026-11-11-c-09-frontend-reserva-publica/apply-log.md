# Apply Log — c-09-frontend-reserva-publica

**Fecha/hora:** 2026-11-11 13:40 (America/Argentina/Buenos_Aires)
**HEAD de referencia:** `01aebee` (`C-07 terminado`, incluye §0 backend y el código frontend de §1–§7)
**Alcance de esta tanda:** verificación final §8 (8.1–8.6). No se implementaron features nuevas; no se commiteó ni pusheó (regla dura 11).

---

## Resumen del apply

Change completo: cliente API tipado con guards de contrato, componentes de búsqueda/slots/formulario/resumen, página pública `/reservar`, página `/cancelar` por token + id opaco, estilos CSS modules mobile-first 360px, accesibilidad (labels/`aria`/`role="alert"`) y delta backend mínimo para que `cancel_url` incluya el `id` del turno (D-10 Opción A).

- **Frontend:** 72 tests en 12 archivos, 0 errores de tipos, build de producción OK.
- **Backend:** suite reportada en la tanda de §0 (commit `01aebee`) con **551 passed**; no se re-ejecutó en §8 porque todas las tareas de §8 son de verificación frontend.
- **Planificación OpenSpec:** válida y completa (`isPlanningComplete: true`, `isComplete: true`).

---

## Detalle por sección

### §0 — Delta backend `cancel_url` con id (D-10 Opción A)

`_cancel_url(token, turno_id)` devuelve `{FRONTEND_URL.rstrip('/')}/cancelar?token={token}&id={turno_id}`; actualizados `reservar()` y `reprogramar()` en `backend/app/modules/turnos/service.py` y `_payload()` en `cancellation_service.py`. El token sigue siendo la única credencial y el `id` es un localizador opaco.

Tests que lo respaldan: `test_reserva_devuelve_token_y_cancel_url_normalizada` (sin doble barra, `token` primero, `id` coincide con el turno), `test_cancelacion_encola_mail_cancelacion_pendiente` (payload con `&id=` y sin `dni`/`telefono`/`obra_social`), fixtures de `test_notificaciones_templates.py`, `test_notificaciones_integracion.py` y `test_turnos_staff.py` (reprogramación). Evidencia de verde: 551 passed en `01aebee`.

### §1 — Cliente API tipado y guards

`shared/api/client.ts` incorpora `ApiErrorDetail` (unión discriminada), `ApiHttpError` con `retryAfter?: number` y `requestWithDetail<T>` sin cambiar `request<T>` ni `getHealth`. `shared/api/reserva.ts` expone `getProfesionales` (sigue `next_cursor`), `getDisponibilidad` (rango del día con offset `-03:00`), `crearTurno` y `cancelarTurno(id, token)` (`DELETE /api/turnos/{id}?token=`) con guards `isProfesionalesResponse`/`isDisponibilidadResponse`/`isTurnoOut`/`isCancelacionOut`.

Tests: `shared/api/__tests__/reserva.test.ts` — **14 tests** (guards, mapeo 400/409/422/403/404/429, rango de día, cancelación con id+token, paginación de dos páginas).

### §2 — Componentes de búsqueda y slots

`ProfesionalSelector`, `useDisponibilidad`, `SlotList`, estados de carga/error/vacío/404/429 y selección de slot.

Tests: `ProfesionalSelector.test.tsx` (2), `useDisponibilidad.test.tsx` (5), `SlotList.test.tsx` (3), `AlternativosList.test.tsx` (2).

### §3 — Formulario de reserva y resumen

Validación local de los cinco campos, mapeo de `400` por campo (`paciente.*` → campo), `inicio`/`duracion_min` como error de slot, `409` con alternativos, resumen `201` con link `token`+`id`, notificaciones encoladas parametrizadas y formateo en `America/Argentina/Buenos_Aires`.

Tests: `ReservaForm.test.tsx` (9), `ReservaResumen.test.tsx` (3), `format.test.tsx` (1).

### §4 — Página `/reservar` e integración de flujos

Flujo feliz `201`, `400` por campo, `409` con alternativos, error de red con reintento, respuesta inesperada, `404` conservando formulario, `429` post-turnos, CTA desde la landing y ausencia de datos sensibles en la URL (incluye remontaje).

Tests: `pages/__tests__/reserva.test.tsx` — **11 tests** (`createMemoryRouter` + `fetch` mockeado en el borde).

### §5 — Routing y delta del shell

`App.tsx` registra `/reservar` y `/cancelar` sin romper `/` ni `*`. Tests: `shell.test.tsx` — **7 tests** (landing con CTA, not-found, 360 sin overflow, error tipado, rutas nuevas).

### §6 — Página `/cancelar`

Confirmación genérica sin datos del turno, `DELETE` por `token`+`id`, manejo de `200`/`403`/`404`/`422`/`429`, sin formulario DNI+teléfono ni "mis turnos", URL solo con `token` e `id`.

Tests: `pages/__tests__/cancelar.test.tsx` — **12 tests**.

### §7 — Estilos CSS modules, accesibilidad y mobile-first

Tokens y reset en `styles.css`; `*.module.css` por componente/página. Accesibilidad: labels con `for`/`id`, `aria-required`, `aria-invalid`, `aria-describedby`, `role="alert"` y orden DOM. Responsive: 360px sin overflow y `min-height >= 44px` escaneando **todos** los `*.module.css`.

Tests: casos R13 dentro de `ReservaForm.test.tsx` + `pages/__tests__/responsive.test.tsx` — **3 tests** (nuevo archivo en esta tanda).

### §8 — Verificación final e integración

Ver tabla de comandos. Todo verde.

---

## Comandos de verificación (ejecutados en esta tanda)

| Task | Comando | Resultado |
|---|---|---|
| 8.1 | `npm test` (en `frontend/`) | **PASS** — 12 archivos, **72 tests passed**, 0 fallos (5.19s) |
| 8.2 | `npx tsc -b` (en `frontend/`) | **PASS** — exit code 0, sin salida (0 errores) |
| 8.2 | `Select-String -Path (Get-ChildItem -Recurse -Include *.ts,*.tsx frontend/src ...) -Pattern '\bany\b'` | **PASS** — 1 única coincidencia, falso positivo: comentario en `frontend/src/shared/api/client.ts:1` ("sin `any`"). Sin usos reales de `any` |
| 8.2 | Búsqueda de usos reales: `(:\s*any\b|<any>\|as any\b\|\bany\[\]\|Array<any>)` y `@ts-ignore\|@ts-expect-error\|@ts-nocheck` | **PASS** — 0 coincidencias |
| 8.3 | `npm run build` (en `frontend/`) | **PASS** — 61 módulos; `index-*.js` **185.58 kB** (gzip 59.99 kB), `index-*.css` **8.59 kB** (gzip 1.59 kB); built in 720ms |
| 8.4 | `git status --short` + `git diff --stat` | **PASS** — solo `frontend/src/**`, `frontend/tsconfig.tsbuildinfo`, `openspec/changes/c-09-frontend-reserva-publica/tasks.md` y el nuevo `frontend/src/pages/__tests__/responsive.test.tsx`. Sin cambios en `openspec/specs/`, `CHANGES.md`, `AGENTS.md`, `CLAUDE.md` ni backend |
| 8.5 | `openspec validate c-09-frontend-reserva-publica --strict` | **PASS** — `Change 'c-09-frontend-reserva-publica' is valid` |
| 8.5 | `openspec status --change c-09-frontend-reserva-publica --json` | **PASS** — `isPlanningComplete: true`, `isComplete: true`, artifacts proposal/specs/design/tasks en `done` |
| 8.6 | (manual, no ejecutado) | **Nota no funcional** — ver riesgos/deuda |

Comando exacto del escaneo de `any` (PowerShell 5.1, sin `rg`):

```powershell
$files = Get-ChildItem -Recurse -Include *.ts,*.tsx frontend/src |
  Where-Object { $_.FullName -notmatch 'node_modules' } | ForEach-Object { $_.FullName }
Select-String -Path $files -Pattern '\bany\b'
```

`git status --short` final:

```
 M frontend/src/features/reserva/__tests__/ReservaForm.test.tsx
 M frontend/src/features/reserva/__tests__/SlotList.test.tsx
 M frontend/src/pages/__tests__/cancelar.test.tsx
 M frontend/src/pages/__tests__/reserva.test.tsx
 M frontend/src/shared/api/__tests__/reserva.test.ts
 M frontend/src/shared/api/reserva.ts
 M frontend/tsconfig.tsbuildinfo
 M openspec/changes/c-09-frontend-reserva-publica/tasks.md
?? frontend/src/pages/__tests__/responsive.test.tsx
```

`frontend/tsconfig.tsbuildinfo` es un **artefacto generado** por `tsc -b` (no es código fuente; está versionado por convención previa del repo).

---

## Fixes destacados

1. **2 rojos en `frontend/src/pages/__tests__/cancelar.test.tsx`**
   - `getByText(/cancelado/)` era ambiguo (múltiples nodos que contienen "cancelado"): se acotó a `getByText(/Estado del turno:\s*cancelado/)`, alineado con el copy real de la página.
   - Lectura de query params: `router.state.location.searchParams` no existe en el tipo de React Router 6.28; se reemplazó por `[...new URLSearchParams(router.state.location.search).keys()]`. El contrato de URL (`token`+`id`, sin datos) se mantiene.
2. **6 errores TS (`tsc -b`) corregidos sin `any` ni `@ts-ignore`**
   - `Router` no es un tipo exportado por `react-router-dom@6.28` en `cancelar.test.tsx` y `reserva.test.tsx`: se reemplazó por `type MemoryRouterInstance = ReturnType<typeof createMemoryRouter>`.
   - `state.location.searchParams` inexistente: se usó `URLSearchParams` explícito.
   - Callbacks de `it.each` y fixtures tipados explícitamente (sin `any`) durante la revisión de tests.
3. **`test-guard`**
   - `SlotList.test.tsx`: `test_seleccionar_slot_habilita_formulario` parametrizado con `it.each` (30 y 45 min) para triangular la duración.
   - `shared/api/__tests__/reserva.test.ts`: triangulación agregada (rango del día con fecha elegida, cancelación con token plano sin parámetros extra, página única sin repetir request).
   - `ReservaForm.test.tsx`: casos R13 de etiquetas, errores anunciados y orden DOM/ARIA agregados; se dejó documentado que `:focus-visible` se verifica manualmente en navegador (no se instala `user-event`).
   - `responsive.test.tsx`: escaneo de **todos** los `*.module.css` (anchos fijos > 360 y `min-height` < 44px), no solo `styles.css`.

---

## Alcance tocado

**Código y tests frontend (commiteados en `01aebee`, este apply solo ajusta):**
- `frontend/src/shared/api/client.ts`, `frontend/src/shared/api/reserva.ts`
- `frontend/src/features/reserva/**` (`errores.ts`, `format.ts`, `types.ts`, `validacion.ts`, `hooks/useDisponibilidad.ts`, `components/*`, `__tests__/*`)
- `frontend/src/pages/Reservar.tsx`, `frontend/src/pages/Cancelar.tsx` (+ `*.module.css`)
- `frontend/src/pages/__tests__/{reserva,cancelar,shell}.test.tsx`
- `frontend/src/styles.css`, `frontend/src/App.tsx`

**Modificados en esta tanda (§8):**
- `frontend/src/features/reserva/__tests__/ReservaForm.test.tsx`
- `frontend/src/features/reserva/__tests__/SlotList.test.tsx`
- `frontend/src/pages/__tests__/cancelar.test.tsx`
- `frontend/src/pages/__tests__/reserva.test.tsx`
- `frontend/src/shared/api/__tests__/reserva.test.ts`
- `frontend/src/shared/api/reserva.ts`
- `frontend/src/pages/__tests__/responsive.test.tsx` (nuevo)
- `frontend/tsconfig.tsbuildinfo` (artefacto generado)
- `openspec/changes/c-09-frontend-reserva-publica/tasks.md`, `apply-log.md`

**Backend (§0, commit `01aebee`, no tocado en esta tanda):** `backend/app/modules/turnos/service.py`, `backend/app/modules/turnos/cancellation_service.py`, `backend/tests/test_reserva_online.py`, `backend/tests/test_cancelacion_paciente.py`, `backend/tests/test_notificaciones_templates.py`, `backend/tests/test_notificaciones_integracion.py`, `backend/tests/test_turnos_staff.py`.

**Sin cambios:** `openspec/specs/`, `CHANGES.md`, `AGENTS.md`, `CLAUDE.md`.

---

## Riesgos y deuda

1. **§8.6 performance <2s de primera carga — medición manual pendiente.**
   - Proxy actual: bundle JS **185.58 kB** (gzip **59.99 kB**) y CSS **8.59 kB** (gzip 1.59 kB). Es un tamaño razonable para una SPA React + Router sin dependencias pesadas, pero **no mide** latencia real de red, TTFB, parse/eval, ni Core Web Vitals.
   - Qué falta medir en navegador: LCP/TTI con throttling (Chrome DevTools, perfil "Fast 3G" y CPU 4x), primera carga en el host de deploy v1, y warm/cold start del backend si aplica. No bloquea CI; no se instalan Lighthouse ni Playwright (restricción v1).
2. **`.pyc` versionados:** 93 archivos `*.pyc` están trackeados en el repo; hoy no ensucian `git status` porque no cambiaron, pero cualquier ejecución de backend puede reintroducir ruido. Follow-up propuesto: `.gitignore` + `git rm --cached` de `*.pyc` en un change de higiene (fuera del alcance de C-09; no ejecutado).
3. **`tsconfig.tsbuildinfo` versionado:** artefacto generado por `tsc -b`; cambia en cada verificación. Evaluar si conviene ignorarlo en un change de higiene.
4. **Cobertura manual no automatizada:** `:focus-visible`, solapamiento real de acciones táctiles a 360px y la medición de performance quedan en revisión manual, documentadas en los tests correspondientes.

---

## Follow-ups

- Completar la medición manual de performance (§8.6) en navegador y registrar el resultado.
- Ejecutar `/opsx:archive c-09-frontend-reserva-publica` y marcar C-09 como completado en `CHANGES.md` (fuera de este paso; requiere orden explícita).
- Change de higiene opcional para `.pyc` y `tsconfig.tsbuildinfo`.
- No commitear ni pushear hasta que el usuario lo pida explícitamente (regla dura 11).

---

## Próximo paso

Change listo para **`/opsx:archive c-09-frontend-reserva-publica`** (la sincronización de specs y el tilde de C-09 en `CHANGES.md` se hacen en ese paso, con orden explícita).

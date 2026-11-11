# Design — c-09-frontend-reserva-publica

## Context

El frontend ya tiene un shell real: React 18 + Vite 5 + React Router 6 + TypeScript estricto, tests con Vitest + Testing Library + jsdom y sin Tailwind ni librería UI. `frontend/src/App.tsx` registra `/` y `*`; `pages/Home.tsx` ya tiene un CTA a `/reservar`; `shared/api/client.ts` expone `ApiError` (`NETWORK_ERROR` | `HTTP_ERROR` | `BAD_PAYLOAD`), `request<T>(url, isT, init)` y `getHealth()`; `styles.css` es una hoja global mínima mobile-first; `vite.config.ts` fija `environment: "jsdom"` y `package.json` ya trae `test`, `build` (`tsc -b && vite build`) y las dependencias de test.

El backend está implementado y archivado. C-09 consume estos contratos ya fijados, con una única excepción mínima de contrato: `cancel_url` pasa a incluir el `id` opaco del turno (D-10, Opción A). El resto de los contratos no se cambia:

- `GET /api/profesionales` → `{ items: [{ id, nombre, especialidad, matricula, duracion_default_min, ultima_actualizacion }], next_cursor }`, solo activos; `getProfesionales()` itera `next_cursor` hasta agotarlo y acumula todas las páginas.
- `GET /api/disponibilidad?profesional_id=&desde=&hasta=` → `{ profesional_id, slots: [{ inicio, fin, duracion_min }], ultima_actualizacion }`; los `slots` ya vienen solo libres (ventanas − bloqueos − ocupados); `404` si el profesional no existe o está inactivo.
- `POST /api/turnos` con `{ profesional_id, inicio, duracion_min?, paciente: { nombre, dni, telefono, obra_social, email } }` → `201` con `{ id, estado, inicio, fin, duracion_min, profesional: { id, nombre }, paciente: { nombre, dni, email }, token_cancelacion, cancel_url, notificaciones_encoladas }`, donde `cancel_url = {FRONTEND_URL sin barra final}/cancelar?token=<token_cancelacion>&id=<turno_id>`; `404` si el profesional no existe o está inactivo.
- Errores `400` con `detail: [{ campo, error, tipo }]`; `409` con `detail: { codigo: "slot_ocupado" | "slot_no_disponible", alternativos: [{ inicio, fin, duracion_min }] }`; `429` con `Retry-After`.
- `DELETE /api/turnos/{id}?token=` → `200` con `{ id, estado, inicio, fin, duracion_min, notificaciones_encoladas, mensaje }`; `403` genérico; `422` con `detail: { codigo, mensaje, contacto? }`; `429` con `Retry-After`.

Decisiones de producto ya cerradas que condicionan el diseño:

- **PB-07 CERRADA**: stack CSS = **CSS modules** (`.module.css` por componente/página, soporte nativo de Vite). No se instala Tailwind ni librería UI; `styles.css` queda como reset + tokens globales.
- **PB-01**: la única vía de cancelación es `/cancelar?token=&id=`; no hay "mis turnos" ni credencial DNI+teléfono. El token sigue siendo la única credencial; el `id` es un localizador opaco (UUID) que no autentica. **PB-01 se interpreta como credencial única; `id` es localizador opaco no credencial (D-10 A); el DELETE conserva solo `?token=`.**
- **PB-02**: los cinco datos del paciente son obligatorios y el mail tiene formato válido; el backend responde 400 por campo. Toda reserva tiene mail: confirmación y recordatorios siempre encolados; no existe aviso "sin mail".
- **PB-08**: reprogramación por paciente fuera de v1; C-09 no la incluye.

Ver `proposal.md` (Why) y `specs/frontend-reserva-publica/spec.md` (requisitos).

## Goals / Non-Goals

**Goals:**

- Implementar las pantallas públicas `/reservar` y `/cancelar` consumiendo los contratos existentes, con un delta backend mínimo y acotado (`cancel_url` con el `id` del turno) para habilitar la cancelación desde el link.
- Extender el cliente HTTP compartido con tipos y guards estrictos (sin `any`) sin romper `request<T>` ni `getHealth`.
- Cubrir los bordes 400/409/422/403/404/429 y los estados de carga/error con una UX mobile-first clara.
- Dejar una estrategia de tests Vitest reproducible: unit de componentes y validación + integración de flujos con `fetch` mockeado en el borde.

**Non-Goals:**

- Migraciones, endpoints nuevos o cambios de contrato distintos del `cancel_url` (el único delta backend es agregar el `id` opaco al link de cancelación, D-10).
- Login, agenda, recepción, admin o reportes (C-10/C-11).
- Reprogramación del paciente (PB-08) y "mis turnos" (PB-01).
- Tailwind, librería UI, estado global, caché de datos o framework de formularios.
- Envío de mail o cualquier lógica de notificaciones: el frontend solo muestra lo que informa el 201.

## Decisions

### D-1. PB-07 cerrada: CSS modules por componente/página

Qué: cada página y componente con estilos propios usa un archivo `*.module.css` importado como objeto de clases (`import styles from "./Reservar.module.css"`). `frontend/src/styles.css` se mantiene como hoja global de reset y tokens (`:root` con colores, espaciado, radios, foco), sin clases de feature. No se instala Tailwind, PostCSS extra ni librería UI.

Por qué sobre alternativas: Vite soporta CSS modules de forma nativa y sin configuración; el alcance de C-09 es chico y no justifica el peso/config de Tailwind. Los CSS modules dan aislamiento por componente y permiten mobile-first con media queries locales. Mantener `styles.css` para reset/tokens evita duplicar normalización y conserva el contrato que ya verifica `shell.test.tsx`.

Alternativa descartada: Tailwind. Motivo: instalación, configuración y una curva de utilidades que no se justifica para dos páginas; además PB-07 pedía decidir explícitamente y el costo/beneficio no cierra. Alternativa descartada: CSS-in-JS. Motivo: dependencia de runtime y patrón nuevo sin necesidad.

Evidencia: `CHANGES.md` C-09 (PB-07 diferida al primer propose frontend) y `knowledge-base/10_preguntas_abiertas.md` PB-07.

### D-2. Rutas y páginas: `/`, `/reservar`, `/cancelar`

Qué: `App.tsx` registra `/`, `/reservar` y `/cancelar`, conservando `*` → `NotFound`. Cada ruta monta una página de `pages/` (`Home`, `Reservar`, `Cancelar`). No hay rutas anidadas ni layouts complejos. `/reservar` no recibe parámetros; `/cancelar` lee `token` e `id` de la query (D-10). La landing mantiene el CTA existente a `/reservar`.

Por qué sobre alternativas: tres rutas planas alcanzan para v1 y respetan el shell actual. Rutas anidadas o un layout con estado compartido agregarían complejidad sin beneficio. La navegación entre búsqueda, formulario y resumen ocurre dentro de `/reservar` sin cambiar de URL, lo que además evita filtrar datos del paciente en la URL (R12).

Alternativa descartada: una ruta por paso (`/reservar/profesional`, `/reservar/datos`, …). Motivo: multiplica URLs y estado, y arriesga datos sensibles en el historial.

### D-3. Cliente API tipado, guards de respuesta y modelo de error

Qué: `shared/api/client.ts` conserva `ApiError`, `request<T>` y `getHealth` sin cambios de firma. Se agrega:
- `ApiErrorDetail` como **unión discriminada**: `FieldError[]` (400) | `{ codigo: string; alternativos: Slot[] }` (409) | `{ codigo: string; mensaje: string; contacto?: string }` (422) | `string` (cuerpo no estructurado) | `unknown` (con guards de estrechamiento). Para `403`/`404` **no se interpreta** el `detail`: se usa solo el `status` para el mensaje genérico.
- `ApiHttpError extends ApiError` con `detail: ApiErrorDetail` y `retryAfter?: number` (segundos parseados de `Retry-After` cuando el `status` es `429`).
- Un helper interno `requestWithDetail<T>(url, isT, init)` que, ante `!response.ok`, intenta parsear el body y lanza `ApiHttpError` con `detail` tipado y `retryAfter`; si el body no parsea, lanza `ApiError` normal. `request<T>` sigue igual para no romper el shell.
- `shared/api/reserva.ts` con funciones `getProfesionales()`, `getDisponibilidad(profesionalId, desde, hasta)`, `crearTurno(body)` y `cancelarTurno(id, token)`. `getProfesionales()` itera `next_cursor` hasta agotarlo (no trunca la lista a la primera página).
- Guards `isProfesionalesResponse`, `isDisponibilidadResponse`, `isTurnoOut`, `isCancelacionOut` construidos con `isRecord` y chequeos explícitos de campos y tipos; nunca `any`, nunca casts ciegos.

Tipos de error discriminados por `status`:
- `400` → `{ detail: FieldError[] }` con `FieldError = { campo: string; error: string; tipo: string }`.
- `409` → `{ detail: { codigo: string; alternativos: Slot[] } }`.
- `422` → `{ detail: { codigo: string; mensaje: string; contacto?: string } }`.
- `403`/`404` → sin datos del turno; no se interpreta `detail`, se trata como mensaje genérico (404 de ruta inexistente se trata igual que 403).
- `429` → `retryAfter?: number` leído de `Retry-After` si está disponible.

Por qué sobre alternativas: el shell depende de `request<T>` y `getHealth`; reemplazar el helper por un `Result` obligaría a tocar código existente y tests. Un helper paralelo mantiene compatibilidad y permite errores ricos solo donde la feature los necesita. Los guards en el borde cumplen el requisito de error tipado del shell y la regla dura 8 (sin `any`).

Alternativa descartada: devolver `unknown` y castear en la página. Motivo: viola la regla dura 8 y vuelve a introducir `any` encubierto. Alternativa descartada: una librería de fetch/query (axios, TanStack Query). Motivo: dependencia nueva sin necesidad para dos pantallas.

### D-4. Estado del formulario y validación por campo

Qué: el formulario vive en un componente `ReservaForm` con estado local (`useReducer` o `useState`) tipado: `FormValues` (los cinco campos), `FormErrors` (mapa `campo → mensaje`) y `status` (`idle | submitting | success | error`). Se valida al enviar y al perder foco: los cinco campos no vacíos (trim) y `email` contra el mismo patrón del backend (`/.+@.+\..+/`, sin ser más estricto, para aceptar `.test`). Si la validación local falla, no se hace `POST`. Si el backend responde `400`, cada entrada `detail[].campo` se normaliza al campo del formulario (por ejemplo `paciente.email` → `email`) y se marca; los valores ingresados se conservan. El foco va al primer campo con error.

Por qué sobre alternativas: validar en cliente evita un viaje inútil y el backend sigue siendo la autoridad (400 por campo). Replicar exactamente el patrón de email del backend evita rechazar datos que el servidor aceptaría. No se usa una librería de formularios porque no está instalada y el formulario es de cinco campos.

Alternativa descartada: validar solo en el backend. Motivo: peor UX y más latencia en mobile. Alternativa descartada: `react-hook-form`/`zod`. Motivo: dependencia nueva no justificada; el proyecto no las usa.

### D-5. Flujo de slots: profesional + fecha

Qué: al montar `/reservar` se cargan los profesionales activos y se muestra un selector. Al elegir profesional y fecha se consulta `GET /api/disponibilidad` con `desde`/`hasta` que cubren ese día calendario en `America/Argentina/Buenos_Aires` (UTC−3, sin horario de verano). El helper construye `YYYY-MM-DDT00:00:00-03:00` y `YYYY-MM-DDT23:59:59-03:00`. La lista muestra solo los `slots` devueltos (el backend ya excluye ocupados y bloqueados), con inicio, fin y duración. Al seleccionar un slot se abre el formulario con ese slot elegido; el `POST` envía `inicio` con el ISO del slot (con offset), `profesional_id` y `duracion_min` del slot.

Por qué sobre alternativas: no se recalcula disponibilidad en cliente: se confía en el contrato público, que ya aplica `[)` y la granularidad. Enviar el rango del día local evita depender de la zona del navegador y mantiene el comportamiento esperado para el consultorio. El `POST` revalida igual: la UI puede ofrecer un slot que se ocupe después (eso se maneja con 409, D-6).

Alternativa descartada: usar `GET /api/profesionales/{id}/agenda` para la vista pública. Motivo: la disponibilidad ya expone exactamente los slots libres con el contrato más simple. Alternativa descartada: calcular el día con la zona del navegador. Motivo: un paciente fuera de Argentina vería otro día; el consultorio opera en Buenos Aires.

### D-6. Manejo tipado de 400, 409, 422 y errores de cancelación

Qué: la UI discrimina por `ApiHttpError.status` y `detail`:
- **400**: mapea solo `detail[].campo` con prefijo `paciente.*` a errores de formulario (`paciente.email` → `email`), conserva valores y slot, no muestra éxito. Un `400` con campo `inicio` o `duracion_min` no se mapea a un input: se muestra como error de slot, se invita a reconsultar disponibilidad y se conservan los datos del paciente.
- **404 de profesional** (en disponibilidad o reserva): muestra un mensaje de profesional no disponible, invita a recargar profesionales o elegir otro y conserva el formulario en el caso de la reserva.
- **409**: muestra un mensaje de "ese horario se ocupó" y la lista de `alternativos` del mismo día; elegir uno actualiza el slot y conserva los datos del formulario para reintentar.
- **422 de cancelación**: si `codigo === "cancelacion_fuera_de_plazo"`, muestra `mensaje` + `contacto` del consultorio y no ofrece reintentar; si `turno_ya_cancelado`/`turno_no_cancelable`, informa el estado **sin contacto y sin reintento**.
- **403/404 de cancelación**: mensaje genérico de link no válido, idéntico para ambos, sin revelar existencia ni datos. El `403` cubre token inválido, turno inexistente o id malformado; el `404` de ruta inexistente se trata igual.
- **429**: mensaje de "demasiados intentos" con espera basada en `retryAfter` (de `Retry-After`) cuando exista, sin reintento automático.
- **NETWORK_ERROR / BAD_PAYLOAD**: mensaje genérico con reintento, sin stack ni detalles internos.

Por qué sobre alternativas: cada código tiene una acción distinta para el paciente; tratarlos todos como "error" perdería la recuperación (reintentar con alternativos) y la información de contacto. Discriminar por `status` + `codigo` mantiene el contrato del backend y permite tests deterministas.

Alternativa descartada: parsear strings del mensaje. Motivo: frágil y dependiente de copy. Alternativa descartada: un solo toast genérico. Motivo: no permite resolver el 409 ni mostrar el contacto del 422.

### D-7. Accesibilidad y mobile-first 360px

Qué: HTML semántico (`main`, `form`, `fieldset`, `button`), `<label htmlFor>` por campo, `aria-invalid` y `aria-describedby` para errores, contenedor de error con `role="alert"`, foco visible con `:focus-visible` en tokens globales y foco programático al primer error o al resumen. Acciones táctiles con `min-height: 44px` en todos los `*.module.css`. Layout fluido: `width: 100%`, `max-width: 100%`, `box-sizing: border-box` (ya en `styles.css`) y sin anchos fijos mayores a 360px; `overflow-x: clip` se mantiene. Media query `min-width: 720px` para ampliar el contenedor en desktop, igual que el shell.

Por qué sobre alternativas: la accesibilidad básica y el target táctil son parte del contrato mobile-first del proyecto; usar tokens globales evita duplicar foco y radios en cada módulo. jsdom no calcula layout real, así que el test de 360px verifica `document.documentElement.scrollWidth` y **escanea todos los `*.module.css`** (anchos fijos >360 y `min-height:44px`), no solo `styles.css`; el solapamiento de acciones se cubre con revisión manual documentada. Sin `user-event` no se puede verificar el foco real en jsdom: el test automatizado cubre labels, `aria` y orden DOM, y `:focus-visible` se valida manualmente en navegador.

Alternativa descartada: confiar solo en estilos inline. Motivo: sin media queries ni foco consistente. Alternativa descartada: test visual con navegador. Motivo: el proyecto no tiene Playwright y C-09 no debe instalar dependencias.

### D-8. Estrategia de tests Vitest

Qué: tres niveles, todos con datos ficticios `.test` y DNI sintéticos (regla dura 12):
1. **Unit de cliente/guards** (`shared/api/__tests__/reserva.test.ts`): respuestas válidas e inválidas, `400/409/422/429` mapeados a `ApiHttpError` con `detail` tipado y `retryAfter`, `403/404` sin interpretar `detail`, `NETWORK_ERROR`, `BAD_PAYLOAD`, y paginación de `getProfesionales()` (dos páginas con `next_cursor`).
2. **Unit de componentes** (`features/reserva/__tests__/*.test.tsx`): render de selector, lista de slots, formulario y resumen; validación local de los cinco campos y mail; estados de carga/error; accesibilidad (labels, `aria-invalid`, `role="alert"` y orden DOM; `:focus-visible` es verificación manual porque no se instala `user-event`); formateo de slots/resumen en `America/Argentina/Buenos_Aires` con el navegador en otra TZ; smoke responsive 360 (scrollWidth + escaneo de todos los `*.module.css`).
3. **Integración de flujos** (`pages/__tests__/reserva.test.tsx`, `cancelar.test.tsx`): `fetch` mockeado en el borde con `vi.stubGlobal("fetch", ...)`, devolviendo `Response` por endpoint en secuencia (profesionales → disponibilidad → turnos, o cancelación). Para aserciones de URL se usa `createMemoryRouter` (no `MemoryRouter` plano) e se inspecciona `router.state.location`; se agrega un caso de recarga/remontaje con la misma `location` y aserción de query. Se usa `fireEvent` de Testing Library (no se instala `user-event`). Cada test se nombra `test_<escenario>_<resultado>` y los casos de borde se parametrizan con `it.each`.

Por qué sobre alternativas: mockear solo el borde HTTP cumple la regla dura 9 (mocks solo en bordes) y permite probar los flujos completos sin backend. No se mockean módulos internos ni el cliente: se ejercita el cliente real contra `fetch` falso. `createMemoryRouter` expone `state.location` real del router, a diferencia de `MemoryRouter` plano, y permite probar la URL sin montar un navegador. La integración con secuencia de respuestas es suficiente para 201/400/404/409/422/429 sin infraestructura extra.

Alternativa descartada: MSW (Mock Service Worker). Motivo: dependencia nueva; `vi.stubGlobal("fetch")` ya se usa en el shell y alcanza. Alternativa descartada: E2E con navegador. Motivo: fuera de scope y sin Playwright.

### D-9. Sin estado global

Qué: no se agrega Context, Redux, Zustand ni caché de datos. El estado de la reserva es local a la página/feature (profesionales, fecha, slots, slot elegido, formulario, resultado). La página de cancelación deriva todo de `token` e `id` de la URL y del resultado de la operación. Al navegar entre rutas se vuelve a consultar lo necesario.

Por qué sobre alternativas: el flujo es de un solo usuario y de vida corta; no hay datos que compartir entre rutas ni necesidad de cachear disponibilidad. Un store global agregaría dependencia, boilerplate y riesgo de filtrar datos del paciente entre pantallas. La regla dura 8 (sin componentes anidados innecesarios) y el alcance chico favorecen estado local.

Alternativa descartada: Context global de reserva. Motivo: acopla páginas y complica los tests; no hay consumidores fuera de `/reservar`. Alternativa descartada: TanStack Query. Motivo: dependencia y capa de caché que C-09 no necesita.

### D-10. Resolución token → turno: RESUELTA (Opción A — id opaco en `cancel_url`)

Qué (contrato exacto): el link de cancelación que arma el backend pasa de `{FRONTEND_URL}/cancelar?token=<token>` a `{FRONTEND_URL sin barra final}/cancelar?token=<token_cancelacion>&id=<turno_id>`. El `token` va primero y el `id` después, separados por `&`, sin doble barra. El `token` sigue siendo la **única credencial**: el `id` es solo un localizador opaco (UUID) del turno y no autentica nada (regla dura 4).

Por qué se eligió la Opción A: resuelve el problema de D-10 sin inventar un endpoint público nuevo. La página `/cancelar` recibe el `id` en la URL, lo usa para invocar el contrato de cancelación ya existente de C-06 —`DELETE /api/turnos/{id}?token=<token>`, sin cambios— y el backend sigue validando que el token corresponda al turno. Se descartó la Opción B (endpoint público de resolución por token) porque agrega superficie pública y lógica nueva al backend para el mismo resultado.

Contrato de la página `/cancelar`:
1. Lee `token` e `id` de la query.
2. Si `id` falta o no es un UUID válido → error genérico de link no válido (no se llama al backend a adivinar).
3. Con `id` válido, muestra una **confirmación genérica** para cancelar (sin profesional, fecha, hora ni datos del paciente) y, al confirmar, llama `DELETE /api/turnos/{id}?token=<token>` (mismo contrato C-06, sin parámetros extra). No se hace un GET previo porque C-06 es DELETE-only.
4. Si el backend responde `403` (token que no corresponde al turno, turno inexistente o id malformado) o `404` (ruta inexistente) → mensaje genérico idéntico, sin revelar existencia ni datos.
5. `422` (fuera de plazo / ya cancelado / no cancelable) conserva el manejo de D-6.
6. El `200` devuelve solo estado/mensaje: la página muestra ese éxito y no datos del turno. Ante error de credencial no renderiza profesional, fecha, hora ni datos del paciente.

Impacto backend (delta mínimo, tarea de apply):
- `backend/app/modules/turnos/service.py`: `_cancel_url(token: uuid.UUID)` (L285) pasa a `_cancel_url(token: uuid.UUID, turno_id: uuid.UUID)` y devuelve `f"{FRONTEND_URL.rstrip('/')}/cancelar?token={token}&id={turno_id}"`.
- Call sites de `_cancel_url` en `service.py`: `reservar()` (L436) y `reprogramar()` (L725), ambos pasando el `id` del turno.
- `backend/app/modules/turnos/cancellation_service.py`: `_payload()` (L80) pasa `turno.id` como segundo argumento (`_cancel_url(turno.token_cancelacion, turno.id)`).
- El payload de notificaciones conserva sus **11 claves**; solo cambia el valor de `cancel_url`.
- Tests que congelan el formato y hay que actualizar en el apply: `backend/tests/test_reserva_online.py:393` y `backend/tests/test_cancelacion_paciente.py:804-805` (ver tasks §0).

Este delta no cambia DB, migraciones ni endpoints: solo el valor del link generado.

### D-11. Estructura de archivos

Qué:
```
frontend/src/
├── pages/
│   ├── Home.tsx                     (CTA existente)
│   ├── Reservar.tsx + Reservar.module.css
│   ├── Cancelar.tsx + Cancelar.module.css
│   └── __tests__/{reserva,cancelar}.test.tsx
├── features/reserva/
│   ├── components/{ProfesionalSelector,FechaSelector,SlotList,ReservaForm,ReservaResumen,AlternativosList}.tsx
│   ├── components/*.module.css
│   ├── hooks/useDisponibilidad.ts
│   ├── types.ts
│   └── __tests__/*.test.tsx
├── shared/api/
│   ├── client.ts                    (extendido, sin romper request<T>/getHealth)
│   ├── reserva.ts                   (endpoints tipados + guards)
│   └── __tests__/reserva.test.ts
└── styles.css                       (reset + tokens globales)
```
Sin barrels: cada import apunta al archivo concreto (regla dura 8). Los componentes no se anidan más de lo necesario; cada uno tiene una responsabilidad y recibe props tipadas.

Por qué: sigue la estructura ya declarada en KB-08 (`features/`, `shared/`, `pages/`) y la convención del repo (sin barrels, imports directos). Mantiene el cliente genérico separado de los endpoints de dominio.

## Risks / Trade-offs

- [Riesgo] El contrato token → turno no existía (D-10) → **Resuelto (Opción A)**: `cancel_url` incluye el `id` opaco del turno y la página llama `DELETE /api/turnos/{id}?token=`; el token sigue siendo la única credencial y un token que no corresponde al id devuelve 403 genérico.
- [Riesgo] Un slot ofrecido se ocupa entre la consulta y el `POST` → Mitigación: 409 con alternativos del mismo día y reintento conservando el formulario (D-6).
- [Riesgo] Diferencia de zona horaria del navegador al construir `desde`/`hasta` → Mitigación: rango del día en `America/Argentina/Buenos_Aires` (UTC−3) y `inicio` enviado con offset (D-5); supuesto documentado.
- [Riesgo] jsdom no calcula layout real y el test de 360px puede dar falsos positivos → Mitigación: mismo enfoque que el shell (scrollWidth + contrato de hoja global + sin anchos fijos > 360) y revisión manual del CSS modules.
- [Riesgo] Validación de email cliente/backend divergente → Mitigación: replicar el patrón exacto del backend (`/.+@.+\..+/`) y aceptar `.test`; el backend sigue siendo la autoridad.
- [Trade-off] Sin estado global, volver atrás puede requerir reconsultar disponibilidad → Mitigación: es barato y evita datos obsoletos; el flujo no necesita persistencia entre rutas.
- [Riesgo] Duplicar lógica de formateo de fechas en varios componentes → Mitigación: helpers tipados en `features/reserva/types.ts` o un módulo de formato local, sin librería de fechas; todos fuerzan `timeZone: "America/Argentina/Buenos_Aires"`.
- [No funcional] Objetivo de performance <2s de primera carga: **no se verifica en CI** (no hay Lighthouse/Playwright); queda como nota de medición manual en navegador, fuera del alcance automatizable de C-09.

## Migration Plan

1. Sin migración de datos ni migraciones de DB. El delta backend es mínimo: `_cancel_url` agrega el `id` del turno al link (`cancel_url`) en reserva, reprogramación y payload de cancelación; no cambia endpoints ni esquema. Desplegar backend y frontend juntos.
2. Orden de apply sugerido: delta backend `cancel_url` con id (§0 de tasks) → cliente/guards → componentes de reserva → página `/reservar` → routing → página `/cancelar` (lee token+id) → estilos/ajustes de accesibilidad.
3. Rollback: redeploy de las versiones anteriores de backend y frontend; no hay estado persistido ni endpoints nuevos que revertir. Los links ya enviados por mail con `&id=` seguirían funcionando porque el `id` no cambia la lógica de cancelación.
4. Verificación: `npm test`, `tsc -b` y `npm run build` en `frontend/`.

## Open Questions

- ~~**D-10 (bloqueante para apply de la página de cancelación)**: endpoint público de resolución por token o `id` en `cancel_url`.~~ **RESUELTA (Opción A)**: el `cancel_url` incluye el `id` opaco del turno (`/cancelar?token=<token>&id=<id>`); el token sigue siendo la única credencial y el backend valida token contra id. Ver D-10.
- ¿El rango `desde`/`hasta` del día debe construirse con offset fijo `-03:00` o con un helper `Intl` de zona? Se adopta UTC−3 por ahora; si el consultorio cambia de zona, se ajusta sin cambiar la spec.

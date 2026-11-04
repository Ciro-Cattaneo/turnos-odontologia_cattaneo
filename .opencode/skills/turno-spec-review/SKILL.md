---
name: turno-spec-review
description: Revisa o prepara proposal, design, specs y tasks de un change de turnos y agenda: detecta reglas ambiguas, bordes faltantes, requisitos sin trazar a RN-* y escenarios no verificables, antes de proponer o implementar. Úsala al redactar o auditar artefactos de C-05 a C-07 y C-09; no usar para revisar código ni tests ya escritos.
---

# turno-spec-review

Revisa artefactos de spec de un change de turnos/agenda y emite hallazgos clasificados con trazabilidad a las reglas de negocio. No reescribe proposal/design/specs/tasks salvo pedido explícito, no inventa reglas ni umbrales, y no revisa código ni tests: eso queda en `test-guard`/`tdd-guide`.

## Cuándo activarla

- Al redactar o revisar `proposal.md`, `design.md`, `specs/*/spec.md` o `tasks.md` de un change de turnos, antes de proponer o implementar.
- Al auditar si una spec cubre concurrencia de slots, mail obligatorio, token de cancelación o ventana de 3 h.
- Al detectar requisitos que no citan ninguna RN-* o escenarios sin resultado observable.
- Al preparar C-05, C-06, C-07 o C-09 y querer un veredicto LISTO / NO LISTO antes de codear.
- No activarla para revisar código ya escrito ni tests: eso es `test-guard`/`tdd-guide`.
- No activarla para cambios fuera de turnos/agenda (auth staff, reportes, deploy).
- No activarla para editar la spec: primero se revisa, después se corrige por pedido explícito.

## Entradas

Leé estas rutas antes de emitir hallazgos:

| Entrada | Ruta |
|---|---|
| Change completo | `openspec/changes/<id>/proposal.md`, `design.md`, `tasks.md`, `specs/*/spec.md` |
| Modelo de datos | `knowledge-base/04_modelo_de_datos.md` (§Paciente, §Turno, §Notificacion, §AuditoriaTurno) |
| Reglas de negocio | `knowledge-base/05_reglas_de_negocio.md` (§RN-TU, §RN-AG, §RN-NO, §RN-AU, §Excepciones globales) |
| Funcionalidades | `knowledge-base/06_funcionalidades.md` (§US-003, §US-004, §US-005) |
| Flujos | `knowledge-base/07_flujos_principales.md` (§Flujo 1, §Flujo 2) |
| Decisiones de gate | `knowledge-base/10_preguntas_abiertas.md` (§PB-01, §PB-02) |
| Scope y governance | `CHANGES.md` (sección del change) |
| Reglas duras | `AGENTS.md` (reglas 1-12) |
| Invariantes ya fijadas | `openspec/specs/turno-lifecycle/spec.md` |

Si falta la carpeta del change o alguno de `proposal.md`, `design.md`, `tasks.md`, `specs/*/spec.md`: registralo como hallazgo bloqueante y no supongas su contenido. Si falta cualquier otra entrada (KB, `CHANGES.md`, spec base o `AGENTS.md`): hallazgo mayor; citá la ruta y la sección ausente y seguí con lo disponible. Nunca completes huecos con reglas de memoria.

## Procedimiento

1. **Inventariar artefactos y requisitos.** Listá los archivos con `Get-ChildItem openspec/changes/<id> -Recurse -File` y extraé cada `### Requirement:` y `#### Scenario:` en un índice con `archivo:línea`. Si no hay specs o no hay ningún `### Requirement:`, emití hallazgo bloqueante y detené el veredicto.
2. **Extraer reglas aplicables.** Leé `knowledge-base/05_reglas_de_negocio.md` y listá las RN-* que tocan el scope declarado en `CHANGES.md`; sumá las reglas duras 1, 2, 4, 5 y 7 de `AGENTS.md` y los gates PB-01/PB-02. Citá cada regla con archivo y código exacto, sin parafrasear el umbral.
3. **Mapear requisito → regla.** Armá una tabla con cada requisito y la RN-* que lo respalda. Todo requisito sin RN-* ni regla dura es `regla no trazable`: no lo interpretes, marcalo para que el autor lo justifique o lo elimine.
4. **Exigir escenarios verificables.** Por cada requisito, verificá al menos 3 escenarios: feliz, error de negocio y borde. Cada uno debe declarar precondición, acción y resultado observable (status HTTP, fila creada/actualizada en DB, notificación encolada, campo de auditoría). Si el resultado no se puede verificar desde API o DB, es `escenario no verificable`. Si un requisito es estructural y un tipo de escenario no aplica, exigí justificación explícita en la spec; sin justificación es hallazgo menor.
5. **Recorrer el checklist de bordes.** Recorré la tabla de la sección siguiente fila por fila y anotá cuáles no aparecen en la spec. Un borde ausente es hallazgo aunque el requisito "suene completo".
6. **Emitir informe y veredicto.** Usá el formato de salida, contá escenarios por tipo y cerrá con `LISTO` o `NO LISTO` más el motivo. No edites artefactos: la corrección sugerida va en el informe, no aplicada.

### Heurísticas de ambigüedad

Marcá `ambigüedad` cuando la spec:

- **No dice qué pasa si** ocurre la rama alterna: falta el caso de error, el estado inválido o la colisión.
- **Admite dos resultados posibles** para la misma precondición: por ejemplo 400 vs 422, crear vs rechazar, o dos códigos de estado distintos.
- **Da un resultado no observable** desde API/DB: "se valida", "se controla" o "queda registrado" sin status, fila, campo ni evento que lo pruebe. Si la vaguedad está en el requisito, clasificá `ambigüedad`; si está en un escenario concreto, clasificá `escenario no verificable`.

## Checklist de bordes del dominio

| Borde | Regla | Qué debe exigir la spec | Señal de omisión |
|---|---|---|---|
| Campo obligatorio faltante (nombre, DNI, teléfono, OS, mail) | RN-TU-01 / duro 1 | 400 con detalle por campo, schema `extra='forbid'` | Dice "valida datos" sin status ni lista de campos |
| Mail con formato inválido | RN-TU-01 / PB-02 / duro 1 | 400 solo en `paciente.email`, distinto del faltante | Agrupa mail con "datos inválidos" o no separa el campo |
| Dos reservas concurrentes al mismo slot | RN-TU-03 / duro 2 | 409 + alternativos del mismo día, garantizado por `EXCLUDE USING gist` o `SELECT FOR UPDATE` | Dice "verifica solape" sin mecanismo en DB ni 409 |
| Duración fuera de la granularidad del profesional | RN-TU-02 / RN-AG-02 | Rechazo explícito (400/422) o normalización declarada contra `duracion_default_min` | Acepta `duracion_min` sin relacionarla con el default |
| Reserva en el borde exacto de la ventana de atención | RN-AG-01 / RN-TU-05 | Define si `fin = hora_hasta` es válido o se rechaza | "Slots dentro de la ventana" sin definir inclusividad |
| Fallo SMTP | RN-NO-02 / duro 5 | Turno creado igual; notificación `pendiente`/`fallida` con 3 reintentos y visible | Condiciona la reserva al envío o no menciona la cola |
| `token_cancelacion` como única credencial | RN-TU-06 / PB-01 / duro 4 | Solo `?token=`, 403 genérico, sin DNI+teléfono ni "mis turnos" | Admite DNI+tel o devuelve 404/401 que revela existencia |
| Cancelación con menos de 3 h | RN-TU-04 | 422 + mensaje y contacto; borde exacto `= 3 h` definido | "No permite cancelar" sin código ni tratamiento del borde |
| Turno ya atendido o cancelado | RN-TU-07 | 422 y lista de estados de origen válidos | No enumera desde qué estados se puede cancelar |
| Soft-delete vs DELETE físico | PB-04 / duro 3 | Soft por defecto; DELETE físico solo con cero turnos | Usa "borrar" sin aclarar cuál de los dos |

## Formato de salida

Emití una tabla Markdown con exactamente estas columnas:

| ID | tipo | ubicación (archivo:sección) | regla citada | hallazgo | corrección sugerida | severidad |
|---|---|---|---|---|---|---|
| H-01 | borde faltante | `specs/reserva-online/spec.md` §Requirement: Reserva sin solape | RN-TU-03 / duro 2 | No define qué devuelve `POST /api/turnos` si el slot se ocupa entre el GET y el POST; no exige exclusión en DB | Agregar escenario concurrente con 409 + alternativos y `EXCLUDE USING gist` | bloqueante |
| H-02 | escenario no verificable | `specs/reserva-online/spec.md` §Scenario: mail inválido | RN-TU-01 / PB-02 | Dice "el mail se valida" sin status ni campo observable | Especificar 400 con detalle solo en `paciente.email` | mayor |

Tipos válidos: `ambigüedad`, `borde faltante`, `regla no trazable`, `escenario no verificable`. Severidades: `bloqueante` (impide implementar o testear, o contradice una regla dura), `mayor` (deja un borde del checklist sin cubrir), `menor` (redacción o trazabilidad incompleta).

Debajo de la tabla, agregá:

- **Escenarios por tipo**: feliz `N`, error de negocio `N`, borde `N`.
- **Veredicto**: `LISTO` si no hay bloqueantes y cada requisito tiene los 3 escenarios; `NO LISTO` en cualquier otro caso, con el motivo en una línea.

## Criterios para revisar el resultado

- Todo hallazgo cita una RN-* o una regla dura concreta y su ubicación `archivo:sección`.
- Ningún hallazgo queda sin corrección sugerida.
- Cada requisito tiene al menos 3 escenarios (feliz, error de negocio, borde) con resultado observable.
- No se agregaron reglas, umbrales ni estados que no estén en la KB o en `AGENTS.md`.
- No se modificó ningún archivo del change: el informe es solo lectura.
- La severidad está justificada por su definición, no por preferencia.

## Límites

- Usá solo datos ficticios en ejemplos y hallazgos (Ley 25.326); nunca nombres, DNI, teléfonos ni mails reales.
- No pegues secretos, credenciales ni contenido de `.env`.
- No consultes datos de pacientes ni de la base.
- No ejecutes código, migraciones ni tests: esta skill analiza artefactos.

## Referencias

- `knowledge-base/04_modelo_de_datos.md`
- `knowledge-base/05_reglas_de_negocio.md`
- `knowledge-base/06_funcionalidades.md`
- `knowledge-base/07_flujos_principales.md`
- `knowledge-base/10_preguntas_abiertas.md`
- `AGENTS.md`
- `CHANGES.md`
- `openspec/specs/turno-lifecycle/spec.md`
- `openspec/changes/archive/2026-10-12-c-02-core-models/specs/` (referencia de formato)

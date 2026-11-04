# Evidencia — invocación real de la skill en una sesión nueva

Fecha: 2026-11-02. Objetivo: cumplir el paso 5 (“en una sesión nueva, comprobar que el agente puede encontrar y utilizar la skill”) y el paso 8 (“evidencia de la invocación de la skill”).

## Método

La sesión donde se creó la skill ya tenía su lista de skills cargada al arrancar, así que no podía invocarla por nombre. Se abrió un **proceso nuevo** de opencode desde la raíz del repo:

```powershell
opencode run --dir . "Invocá la skill turno-spec-review. Revisá SOLO el Requirement 'Anti-solape y colisión concurrente con un solo ganador' de openspec/changes/c-05-reserva-online-backend/specs/reserva-online/spec.md, contrastándolo con AGENTS.md regla dura 2 y knowledge-base/05_reglas_de_negocio.md RN-TU-03. Devolvé la tabla de hallazgos con el formato de la skill (si no hay, decí 'sin hallazgos') y el veredicto LISTO/NO LISTO. Solo lectura: no edites archivos, no corras tests, no hagas commits."
```

## Qué hizo el agente (traza resumida)

1. Invocó la herramienta `skill` con `name="turno-spec-review"` → **se cargó** (`Skill "turno-spec-review"`).
2. Siguió el procedimiento de la skill: `Grep "RN-TU-03"` en la KB, inventario de artefactos del change con `Get-ChildItem`, índice de `### Requirement:`/`#### Scenario:` de la spec, lectura de la sección R5 (líneas 165-204) y `Grep "NUNCA SQL concatenado"` en `AGENTS.md` (regla dura 2).
3. Contrastó con `design.md` §D-2/D-12, `proposal.md`, `CHANGES.md` §C-05 y RN-TU-03.
4. No modificó archivos (solo lecturas y búsquedas).

## Resultado obtenido

```
Sin hallazgos.

| ID | tipo | ubicación | regla citada | hallazgo | corrección sugerida | severidad |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

- Escenarios por tipo (Requirement "Anti-solape y colisión concurrente con un solo ganador",
  spec.md:173-199): feliz 1 (contiguas → 201), error de negocio 2 (slot ocupado y EXCLUDE
  fuera del lock → 409), borde 1 (segunda transacción espera lock y termina en 409).
- Trazabilidad: cubre RN-TU-03 (409 + alternativos del mismo día, un solo ganador) y regla
  dura 2 (EXCLUDE no_solape_prof como autoridad final + SELECT ... FOR UPDATE en la reserva),
  con resultados observables (status, filas, rollback de paciente).
- Veredicto: LISTO — sin bloqueantes, sin bordes del checklist faltantes y con los 3 tipos
  de escenario presentes.
```

## Qué aportó al change

- Confirma de forma independiente que la corrección de H-01 quedó bien: el requirement de anti-solape ya nombra el lock **y** el EXCLUDE, y los cuatro escenarios cubren feliz, error de negocio y borde con resultados observables.
- Verifica el descubrimiento y la ejecución de la skill desde el repo, sin instalación global ni referencias manuales.
- No reemplaza la revisión completa de `02`/`03`: es una verificación acotada de un requirement, hecha en un proceso limpio. Mismo modelo y mismas fuentes, así que no es una segunda opinión independiente en sentido estricto.

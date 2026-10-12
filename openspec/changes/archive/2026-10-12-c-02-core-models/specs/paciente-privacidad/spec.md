# Spec Delta — paciente-privacidad

## Purpose

Implementa el gate PB-04 HÍBRIDO y la Ley 25.326 para datos de salud: desactivar en lugar de borrar, prohibir el borrado físico con historial, anonimizar bajo procedimiento y auditar todo sin permitir reescritura.

## ADDED Requirements

### Requirement: Baja de paciente es soft-delete por defecto

The system SHALL deactivate patients via `activo=false` (UI says "desactivar") and SHALL keep their `Turno` history untouched; listings of active patients MUST exclude deactivated ones.

#### Scenario: Desactivar paciente conserva sus turnos

- **DADO** un `Paciente` activo con 2 turnos históricos
- **CUANDO** se lo desactiva (`activo=false`)
- **ENTONCES** el paciente queda inactivo, sus 2 turnos siguen legibles como estadística y deja de aparecer en listados de activos

#### Scenario: Reactivar restaura visibilidad sin perder historial

- **DADO** un `Paciente` desactivado con turnos históricos
- **CUANDO** se lo reactiva (`activo=true`)
- **ENTONCES** vuelve a aparecer en listados de activos con su historial intacto

#### Scenario: EDGE — desactivar paciente ya desactivado es idempotente

- **DADO** un `Paciente` ya inactivo (`activo=false`)
- **CUANDO** se repite la desactivación
- **ENTONCES** el sistema lo acepta sin error ni duplicación de auditoría espuria (o con auditoría de no-op documentada) y el historial sigue intacto

### Requirement: DELETE físico solo con cero turnos

The system SHALL allow physical `DELETE` of a `Paciente` ONLY when zero `Turno` rows reference it; otherwise it MUST refuse the delete.

#### Scenario: Borrar paciente sin turnos es permitido

- **DADO** un `Paciente` sin ningún `Turno` asociado
- **CUANDO** se solicita su `DELETE` físico
- **ENTONCES** la fila se elimina y no quedan referencias huérfanas

#### Scenario: Borrar paciente con turnos es rechazado

- **DADO** un `Paciente` con al menos un `Turno` (cualquier estado)
- **CUANDO** se solicita su `DELETE` físico
- **ENTONCES** el sistema rechaza el borrado (FK/restricción app) y el paciente más sus turnos permanecen intactos

#### Scenario: EDGE — borrar paciente cuyo único turno fue cancelado sigue prohibido

- **DADO** un `Paciente` cuyo único `Turno` está en `estado=cancelado`
- **CUANDO** se solicita su `DELETE` físico
- **ENTONCES** el sistema lo rechaza porque los cancelados se conservan para reportes/ausentismo (RN-TU, Excepciones globales)

### Requirement: Anonimización manual Ley 25.326 documentada sin UI v1

The system SHALL document a manual admin-only anonymization procedure (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos kept as statistics) with no v1 UI and no automatic execution.

#### Scenario: Anonimizar a pedido conserva estadísticas sin datos personales

- **DADO** un pedido Ley 25.326 sobre un `Paciente` con turnos
- **CUANDO** un admin ejecuta el procedimiento documentado (script/endpoint admin)
- **ENTONCES** el paciente queda con nombre `"Eliminado #id"` y `dni/tel/mail` en NULL mientras sus turnos permanecen como filas estadísticas sin vínculo identificable

#### Scenario: Anonimización no toca otros pacientes ni rompe FK

- **DADO** dos pacientes A (objeto del pedido) y B
- **CUANDO** se anonimiza A
- **ENTONCES** B conserva todos sus datos y ninguna FK de turnos queda huérfana

#### Scenario: Sin UI v1 para anonimizar

- **DADO** cualquier usuario (incluido staff) en v1
- **CUANDO** busca una acción UI de "anonimizar"/"derecho al olvido"
- **ENTONCES** no existe tal acción en la UI; solo el procedimiento admin documentado fuera de la UI

### Requirement: AuditoriaTurno es append-only

The system SHALL allow only INSERT on `AuditoriaTurno` from the app (crear/editar/cancelar/forzar_cancelacion/reprogramar con actor y timestamp); UPDATE and DELETE from the app MUST be refused.

#### Scenario: Cada mutación staff escribe auditoría

- **DADO** un `Turno` existente
- **CUANDO** staff lo muta (crear/editar/cancelar/forzar/reprogramar)
- **ENTONCES** aparece una fila `AuditoriaTurno` con `turno_id`, `actor_id`, `accion` y `created_at`, legible en el historial de la ficha

#### Scenario: UPDATE de auditoría por app es rechazado

- **DADO** una fila `AuditoriaTurno` existente
- **CUANDO** la app intenta modificarla (`UPDATE`)
- **ENTONCES** el sistema rechaza la operación (permiso app/trigger) y la fila queda intacta

#### Scenario: DELETE de auditoría por app es rechazado

- **DADO** una fila `AuditoriaTurno` existente
- **CUANDO** la app intenta eliminarla (`DELETE`)
- **ENTONCES** el sistema rechaza la operación y la fila permanece como trail permanente

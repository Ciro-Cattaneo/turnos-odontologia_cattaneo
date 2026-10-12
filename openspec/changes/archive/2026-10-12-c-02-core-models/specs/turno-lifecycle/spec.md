# Spec Delta — turno-lifecycle

## Purpose

Fija las invariantes del ciclo de vida de Turno a nivel modelo para que ningún change posterior pueda crear turnos sin estado válido, sin origen, sin token único o con rango temporal inválido.

## ADDED Requirements

### Requirement: Turno exige estado, origen y token_cancelacion único

The system SHALL require every `Turno` to carry `estado` in `(reservado, confirmado, cancelado, atendido, ausente)`, `origen` in `(online, recepcion)` and a non-null globally unique `token_cancelacion` UUID.

#### Scenario: Crear turno reservado online con token genera fila válida

- **DADO** un profesional y un paciente existentes
- **CUANDO** se persiste un `Turno` con `estado=reservado`, `origen=online`, `inicio/fin` válidos y `token_cancelacion` UUID nuevo
- **ENTONCES** la fila persiste con `created_at` poblado y el token es recuperable por `ux_turno_token`

#### Scenario: Token duplicado o nulo es rechazado

- **DADO** un `Turno` existente con `token_cancelacion = T`
- **CUANDO** se intenta persistir otro `Turno` con el mismo `T` o con token NULL
- **ENTONCES** el sistema rechaza la fila por violación de `UNIQUE`/`NOT NULL` de `token_cancelacion`

#### Scenario: Estado u origen fuera de enum es rechazado

- **DADO** un profesional y un paciente existentes
- **CUANDO** se intenta persistir un `Turno` con `estado=en_espera` o `origen=whatsapp`
- **ENTONCES** el sistema rechaza la fila por violación del enum correspondiente

### Requirement: Rango temporal válido con fin mayor a inicio

The system SHALL reject any `Turno` where `fin <= inicio` and SHALL persist `duracion_min` consistent with `fin - inicio`.

#### Scenario: Turno con fin anterior a inicio es rechazado

- **DADO** un profesional y un paciente existentes
- **CUANDO** se intenta persistir un `Turno` con `fin <= inicio`
- **ENTONCES** el sistema rechaza la fila por violación del CHECK `fin > inicio`

#### Scenario: EDGE — turno de duración cero en el borde es rechazado

- **DADO** un profesional y un paciente existentes
- **CUANDO** se intenta persistir un `Turno` con `inicio = fin = 10:30` (rango vacío `[10:30,10:30)`)
- **ENTONCES** el sistema lo rechaza por `fin > inicio`, aunque no solape con nada

#### Scenario: Duración inconsistente con el rango es rechazada

- **DADO** un profesional y un paciente existentes
- **CUANDO** se intenta persistir un `Turno` de 10:00 a 10:30 con `duracion_min = 45`
- **ENTONCES** el sistema rechaza la fila porque `duracion_min` debe igualar `fin - inicio` en minutos

### Requirement: Canal y columnas post-v1 con defaults seguros

The system SHALL default `canal_recordatorio` to `mail` and SHALL keep post-v1 columns `pago_estado` and `lista_espera_pos` nullable with no v1 logic attached.

#### Scenario: Turno sin canal explicita mail por defecto

- **DADO** un profesional y un paciente existentes
- **CUANDO** se persiste un `Turno` sin indicar `canal_recordatorio`
- **ENTONCES** la fila persiste con `canal_recordatorio = mail`

#### Scenario: Columnas post-v1 nulas no afectan la reserva v1

- **DADO** un profesional y un paciente existentes
- **CUANDO** se persiste un `Turno` con `pago_estado = NULL` y `lista_espera_pos = NULL`
- **ENTONCES** la fila persiste y ningún CHECK ni lógica v1 exige valores en esas columnas

#### Scenario: Canal futuro distinto de mail es rechazado en v1

- **DADO** un profesional y un paciente existentes
- **CUANDO** se intenta persistir un `Turno` con `canal_recordatorio = whatsapp`
- **ENTONCES** el sistema rechaza la fila por violación del enum v1 (la extensión a WA es post-v1 y requiere migración)

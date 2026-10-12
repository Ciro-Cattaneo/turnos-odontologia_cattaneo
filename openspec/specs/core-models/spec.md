# core-models Specification

## Purpose

Persiste las ocho entidades del dominio odontológico con sus constraints e índices para que agenda, reserva, notificaciones y auditoría tengan una base de datos confiable y sin solapamientos.

## Requirements

### Requirement: Entidades core persisten con atributos e índices KB-04

The system SHALL persist `Paciente, Profesional, Disponibilidad, Bloqueo, Turno, Notificacion, UsuarioStaff, AuditoriaTurno` with the attributes, UNIQUE/CHECK/FK constraints and indexes defined in KB-04.

#### Scenario: Crear las ocho entidades válidas persiste

- **DADO** una base Postgres 16 migrada a `001_core_models`
- **CUANDO** se insertan un `Profesional`, `Paciente`, `Disponibilidad`, `Bloqueo`, `Turno` (reservado), `Notificacion` (pendiente), `UsuarioStaff` (recepcion) y `AuditoriaTurno` (crear) válidos y relacionados
- **ENTONCES** las ocho filas persisten y son legibles por PK con sus FK resueltas

#### Scenario: DNI duplicado viola UNIQUE y es rechazado

- **DADO** un `Paciente` existente con `dni = "30123456"`
- **CUANDO** se intenta persistir otro `Paciente` con el mismo `dni`
- **ENTONCES** el sistema rechaza la segunda inserción por violación de `UNIQUE(dni)` (`ux_paciente_dni`) sin crear la fila

#### Scenario: Disponibilidad con hora_desde >= hora_hasta es rechazada

- **DADO** un `Profesional` activo
- **CUANDO** se intenta persistir una `Disponibilidad` con `hora_desde >= hora_hasta`
- **ENTONCES** el sistema rechaza la fila por violación del CHECK `hora_desde < hora_hasta`

### Requirement: Anti-solape EXCLUDE gist por profesional en estados activos

The system SHALL reject overlapping `Turno` ranges for the same `profesional_id` when both overlap in `tstzrange(inicio, fin)` and both are in `('reservado','confirmado')`, using `EXCLUDE USING gist` with half-open `[)` semantics.

#### Scenario: Dos turnos activos solapados son rechazados

- **DADO** un `Turno` `reservado` del profesional P de 10:00 a 10:30 (UTC persistido)
- **CUANDO** se intenta persistir otro `Turno` `reservado` de P de 10:15 a 10:45
- **ENTONCES** el sistema rechaza la segunda fila por la exclusión anti-solape

#### Scenario: EDGE — turno que empieza exactamente cuando termina otro es permitido

- **DADO** un `Turno` `confirmado` del profesional P de 10:00 a 10:30 (rango half-open `[10:00, 10:30)`)
- **CUANDO** se persiste otro `Turno` `reservado` de P de 10:30 a 11:00
- **ENTONCES** el sistema acepta ambas filas porque los rangos `[)` no se intersectan en el borde (`&&` es falso en el punto exacto)

#### Scenario: Solape con turno cancelado es permitido

- **DADO** un `Turno` `cancelado` del profesional P de 10:00 a 10:30
- **CUANDO** se persiste un `Turno` `reservado` de P de 10:15 a 10:45
- **ENTONCES** el sistema acepta la fila porque el predicado `WHERE (estado IN ('reservado','confirmado'))` excluye al cancelado

#### Scenario: Mismo horario con distinto profesional es permitido

- **DADO** un `Turno` `reservado` del profesional P1 de 10:00 a 10:30
- **CUANDO** se persiste un `Turno` `reservado` del profesional P2 en el mismo rango
- **ENTONCES** el sistema acepta la fila porque la exclusión compara `profesional_id WITH =`

#### Scenario: Colisión concurrente solo deja un ganador

- **DADO** dos transacciones concurrentes que intentan reservar el mismo slot activo de P
- **CUANDO** ambas hacen commit casi simultáneo
- **ENTONCES** una persiste y la otra es rechazada por la exclusión (una sola fila ganadora, sin doble reserva)

### Requirement: Migración 001 y seeds reproducibles

The system SHALL provide Alembic revision `001_core_models` (upgrade + downgrade) and seeds: admin inicial desde env y `seed_demo.py` solo staging con datos ficticios.

#### Scenario: Upgrade y downgrade de 001 son limpios

- **DADO** una base Postgres 16 vacía
- **CUANDO** se aplica `alembic upgrade head` y luego `alembic downgrade -1`
- **ENTONCES** el upgrade crea las 8 tablas + enums + EXCLUDE sin error y el downgrade las elimina sin residuos

#### Scenario: Seed crea admin desde env sin duplicar

- **DADO** `ADMIN_EMAIL`/`ADMIN_PASSWORD` configurados y base migrada vacía
- **CUANDO** se ejecuta el seed inicial dos veces
- **ENTONCES** existe exactamente un `UsuarioStaff` admin con ese email (idempotente, sin duplicados)

#### Scenario: seed_demo solo staging con datos ficticios

- **DADO** entorno staging con base migrada
- **CUANDO** se ejecuta `seed_demo.py`
- **ENTONCES** existen 2 profesionales y 20 turnos ficticios, ningún dato real de paciente, y el script documenta que NUNCA se ejecuta en producción

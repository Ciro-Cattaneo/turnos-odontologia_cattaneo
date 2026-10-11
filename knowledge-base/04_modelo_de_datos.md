# Modelo de Datos

## Dominios

- **Personas**: pacientes (sin login v1), profesionales, usuarios staff.
- **Agenda**: disponibilidades/horarios por profesional, bloqueos, sobreturnos (solo staff).
- **Turnos**: reserva, estados, cancelación, auditoría.
- **Notificaciones**: mails encolados/enviados (v1); canal extensible a WA post-v1.
- **(Reservado post-v1)**: pagos/seña, lista de espera, historia clínica — no modelados en v1 salvo columnas de extensión.

## ERD (textual)

```
Profesional 1───N Disponibilidad (ventanas semanales + excepciones)
Profesional 1───N Turno N───1 Paciente
Profesional 1───N Bloqueo
Turno 1───N Notificacion
Turno 1───N AuditoriaTurno (quién/qué/cuándo)
UsuarioStaff N───1 Rol (recepcion | odontologo | admin); odontologo linkea a Profesional
```

Constraint crítico: solapamiento se previene en capa app + constraint de exclusión Postgres (rango tstzrange por profesional, ver RN-TU-03).

## Entidades

### Paciente
- Atributos: `id UUID PK`, `dni VARCHAR(20) NOT NULL`, `telefono VARCHAR(30) NOT NULL`, `obra_social VARCHAR(100) NOT NULL` (texto libre v1), `nombre VARCHAR(120) NOT NULL`, `email VARCHAR(160) NOT NULL` (OBLIGATORIO — GATE 2026-10-11 PB-02; formato válido, toda reserva encola confirmación+recordatorios), `activo BOOL DEFAULT true` (soft-delete default, UI "desactivar" — PB-04), `created_at`, `updated_at`.
- Relaciones: 1───N Turno.
- Constraints: `UNIQUE(dni)` (un paciente físico = un registro; el teléfono puede cambiar); teléfono formato validado laxo (solo dígitos/`+`/espacios, ≥8 chars).
- Índices: `ux_paciente_dni`, `ix_paciente_telefono`.

### Profesional
- Atributos: `id UUID PK`, `nombre`, `matricula VARCHAR(50) NULL`, `especialidad VARCHAR(100) NULL`, `duracion_default_min INT DEFAULT 30`, `activo BOOL DEFAULT true`.
- Relaciones: 1───N Disponibilidad, Turno, Bloqueo; 1───1 UsuarioStaff (nullable, solo si el profesional loguea).
- Índices: `ix_profesional_activo`.

### Disponibilidad (ventana semanal recurrente)
- Atributos: `id UUID PK`, `profesional_id FK`, `dia_semana SMALLINT 0-6`, `hora_desde TIME`, `hora_hasta TIME`, `vigente_desde DATE NULL`, `vigente_hasta DATE NULL`.
- Constraints: `hora_desde < hora_hasta`; sin solape entre ventanas del mismo profesional+día (validación app + test).
- Índices: `ix_disponibilidad_prof_dia`.

### Bloqueo (excepción: feriado, vacaciones, sobreturno negativo)
- Atributos: `id UUID PK`, `profesional_id FK`, `desde TIMESTAMPTZ`, `hasta TIMESTAMPTZ`, `motivo TEXT`, `creado_por FK staff`.
- Los slots se computan como: ventanas recurrentes − bloqueos − turnos ocupados.

### Turno
- Atributos: `id UUID PK`, `profesional_id FK NOT NULL`, `paciente_id FK NOT NULL`, `inicio TIMESTAMPTZ NOT NULL`, `fin TIMESTAMPTZ NOT NULL`, `duracion_min INT NOT NULL DEFAULT 30`, `estado ENUM(reservado, confirmado, cancelado, atendido, ausente) DEFAULT reservado`, `origen ENUM(online, recepcion) NOT NULL`, `token_cancelacion UUID NOT NULL UNIQUE` (link de cancelación por mail), `notas TEXT NULL`, `canal_recordatorio ENUM(mail) DEFAULT mail` (extensible a `whatsapp` post-v1), `created_at`, `updated_at`.
- Relaciones: N───1 Profesional/Paciente; 1───N Notificacion/AuditoriaTurno.
- Constraints: `fin > inicio`; `duracion = fin - inicio`; exclusión anti-solape por profesional para estados activos (`reservado, confirmado`) — `EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin) WITH &&) WHERE (estado IN ('reservado','confirmado'))`.
- Índices: `ix_turno_prof_inicio (profesional_id, inicio)`, `ix_turno_estado_inicio`, `ux_turno_token`.
- **Puerta post-v1 (columnas reservadas, nullable, sin lógica)**: `pago_estado VARCHAR(20) NULL`, `lista_espera_pos INT NULL`. No se usan en v1; evitan migración rompedora después.

### Notificacion
- Atributos: `id UUID PK`, `turno_id FK`, `canal ENUM(mail)`, `tipo ENUM(confirmacion, recordatorio_24h, recordatorio_2h, cancelacion)`, `estado ENUM(pendiente, enviada, fallida)`, `intentos SMALLINT DEFAULT 0`, `payload JSONB`, `enviada_at NULL`, `error TEXT NULL`.
- Índices: `ix_notif_estado (estado) WHERE estado='pendiente'` para el worker.

### UsuarioStaff
- Atributos: `id UUID PK`, `email CITEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`, `rol ENUM(recepcion, odontologo, admin)`, `profesional_id FK NULL`, `activo BOOL DEFAULT true`.
- Seed: un admin inicial vía env vars (ver 08).

### AuditoriaTurno
- Atributos: `id UUID PK`, `turno_id FK`, `actor_id FK NULL` (staff o NULL=paciente), `accion VARCHAR(40)` (crear/editar/cancelar/forzar_cancelacion/reprogramar), `detalle JSONB`, `created_at`.
- Append-only (sin UPDATE/DELETE por app).

## Seed data inicial

- Roles fijos (enum, sin tabla extra o tabla `roles` con 3 filas).
- 1 usuario admin (de `ADMIN_EMAIL`/`ADMIN_PASSWORD` iniciales, rotar al primer login).
- Profesionales reales del consultorio (carga manual recepción, N chico).
- Disponibilidades semanales por profesional (carga manual).
- Sin pacientes de ejemplo en producción; en staging un script `seed_demo.py` con 2 profesionales + 20 turnos ficticios.

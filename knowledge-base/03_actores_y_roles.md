# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|-------|-------------|-----------------|
| Paciente | Persona que reserva turno odontológico; mayoría desde el celular | Web pública responsive, sin login en v1: ve slots libres, reserva con nombre+DNI+teléfono+OS+mail (los 5 obligatorios — PB-02), cancela con ≥3h solo vía link `token_cancelacion` (PB-01) |
| Odontólogo/a | Profesional con agenda propia; hay varios desde el día 1 | Web con login: ve su agenda día/semana, estados de turnos; lectura + confirmación/atención (no borra turnos de otros) |
| Recepción | Personal que gestiona la agenda y valida datos | Web con login: CRUD completo de turnos, edita disponibilidades y duraciones, fuerza cancelaciones con auditoría |
| Admin | Dueño/responsable (puede coincidir con recepción en consultorio chico) | Web con login: todo lo de recepción + gestión de profesionales/usuarios/horarios y reportes básicos |
| Sistema (worker) | Actor técnico | Encola y envía recordatorios mail con reintentos; registra resultado por turno |

## RBAC — Matriz de permisos

RBAC simple rol → permisos (decisión Ronda 2 autónoma: ABAC innecesario a esta escala; reevaluar si multi-sucursal llega).

| Rol | Turnos (crear) | Turnos (leer) | Turnos (editar/reprogramar) | Turnos (borrar/cancelar) | Disponibilidad | Profesionales/usuarios | Reportes |
|-----|----------------|---------------|------------------------------|--------------------------|----------------|------------------------|----------|
| Paciente (público) | Propio (vía reserva online) | Propio (vía `token_cancelacion`) | No (solo cancela el propio ≥3h) | Propio ≥3h | Lee slots libres | Lee lista pública profesionales | No |
| Odontólogo | No | Propios (su agenda) | Marca estado de los propios (confirmado/atendido) | No (pide a recepción) | Lee la propia | Lee | Propios básicos |
| Recepción | Sí (cualquiera) | Todos | Sí | Sí (incl. forzar <3h con auditoría) | CRUD | Lee | Básicos |
| Admin | Sí | Todos | Sí | Sí | CRUD | CRUD | Todos + export |

Herencia: Admin ⊇ Recepción ⊇ (lectura). Odontólogo no hereda de recepción. Sin permisos a nivel de recurso individual en v1 (todos los recepcionistas ven todos los profesionales — escala <50 lo permite).

## Rutas públicas

- `GET /` — landing + acceso a reserva.
- `GET /reservar` — buscador de slots (por profesional/fecha).
- `POST /api/turnos` — crear reserva (rate-limited, captcha liviano si abuso).
- `GET /cancelar?token=` — cancelación solo por link de mail con `token_cancelacion` (GATE PB-01; sin DNI+teléfono, sin "mis turnos").
- `GET /api/disponibilidad`, `GET /api/profesionales` — lectura pública.
- `GET /api/health` — salud.

Todo `/admin/*`, `/api/turnos` staff (PUT/DELETE sin token de paciente), `/api/disponibilidad` escritura y `/api/reportes` requieren auth staff.

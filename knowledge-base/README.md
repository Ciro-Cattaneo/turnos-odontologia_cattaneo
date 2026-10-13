# turnos-odontologia_cattaneo — Base de Conocimiento

Base generada en modo interactivo (Ronda 1 respondida: `1:b 2:a 3:c 4:a 5:d`) + Discovery previo (`docs/discovery/checklist-11-puntos.md`, `docs/discovery/market-research-odontologia-AR.md`). Stack: FastAPI + React + Postgres. MVP: flujo base + mail; WA/MP/lista de espera/HC fuera de v1. Prioridad: costo mínimo.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack FastAPI+React+PG, arquitectura monolitica, integraciones (mail v1; WA/MP reservados), API REST |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Paciente/odontólogo/recepción/admin, RBAC simple, rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | Paciente/Profesional/Disponibilidad/Bloqueo/Turno/Notificacion/Staff/Auditoría, ERD, seed |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-TU/RN-AG/RN-NO/RN-PA/RN-AU (5 campos obligatorios incl. mail, solo token, ≥3h, anti-solape, 30min, solo mail, híbrido PB-04) |
| [06_funcionalidades.md](06_funcionalidades.md) | US-001…US-011 por épica + NO-US post-v1 |
| [07_flujos_principales.md](07_flujos_principales.md) | Reserva, cancelación, CRUD recepción, worker mail, login staff |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, directorios, seguridad, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | DD-01…DD-07 + SU-01…SU-04 |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | IN-01/IN-02 + PB-01…PB-08 (Ronda 2 parcial autónoma) |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Agenda multi-profesional para un consultorio odontológico AR a costo mínimo: reserva online sin login (5 campos obligatorios incl. mail, identidad por turno = token), cancela ≥3h solo con token, anti-solape en Postgres, recordatorios solo mail por workers livianos (APScheduler en-proceso). WhatsApp, seña MP, lista de espera e historia clínica quedan explícitamente post-v1 con puertas de extensión reservadas.

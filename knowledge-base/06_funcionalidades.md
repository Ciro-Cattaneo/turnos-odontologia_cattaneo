# Funcionalidades

Organizadas por épica. Formato US-NNN con criterios de aceptación testeables. Reglas trazadas a 05.

## Épica 1: Agenda y disponibilidad (base)

### US-001 — Ver agenda por profesional (día/semana)
**Como** odontólogo/recepción **Quiero** ver la agenda de un profesional en vista día y semana **Para** organizar la jornada.
**Criterios de aceptación**:
- [ ] CA-1: Vista día muestra slots ocupados/libres/bloqueados con estado y paciente (staff).
- [ ] CA-2: Vista semana del profesional con navegación por fecha.
- [ ] CA-3: Multi-profesional: selector cambia de agenda sin recargar datos ajenos.
**Reglas relacionadas**: RN-AG-01, RN-AG-02, RN-TU-05.

### US-002 — Mantener disponibilidades y bloqueos
**Como** recepción **Quiero** crear/editar ventanas semanales y bloqueos con motivo **Para** que los slots ofrecidos sean reales.
**Criterios de aceptación**:
- [ ] CA-1: CRUD de ventanas (día, desde/hasta, vigencia).
- [ ] CA-2: Crear bloqueo con motivo; los slots afectados dejan de ofrecerse.
- [ ] CA-3: La UI muestra "última actualización" por profesional (mitiga riesgo principal).
**Reglas relacionadas**: RN-AG-01, RN-AG-03, RN-TU-05.

## Épica 2: Reserva online (paciente)

### US-003 — Ver horarios libres
**Como** paciente **Quiero** ver horarios libres por profesional y fecha desde el celular **Para** reservar sin llamar.
**Criterios de aceptación**:
- [ ] CA-1: Responde en <2s en 4G con lista de slots (profesional, fecha, hora, duración).
- [ ] CA-2: No muestra slots bloqueados ni ocupados.
- [ ] CA-3: Mobile-first: usable a 360px sin zoom horizontal.
**Reglas relacionadas**: RN-TU-05, RN-AG-02.

### US-004 — Reservar turno sin login
**Como** paciente **Quiero** reservar con nombre+DNI+teléfono+OS+mail (los 5 obligatorios) **Para** asegurar mi turno.
**Criterios de aceptación**:
- [ ] CA-1: Sin los 5 obligatorios no se crea (400 con campo marcado; mail con formato válido sino 400 en ese campo).
- [ ] CA-2: Slot ocupado concurrente → 409 + alternativos del mismo día (RN-TU-03).
- [ ] CA-3: Reserva exitosa crea turno `reservado`, encola confirmación mail + recordatorios (siempre — toda reserva tiene mail) y devuelve resumen + link de cancelación.
**Reglas relacionadas**: RN-TU-01, RN-TU-03, RN-TU-06, RN-NO-01.

### US-005 — Cancelar con ≥3h
**Como** paciente **Quiero** cancelar mi turno con ≥3h de anticipación **Para** liberar el slot.
**Criterios de aceptación**:
- [ ] CA-1: Cancelación ≥3h → estado `cancelado` + slot liberado + mail de confirmación.
- [ ] CA-2: Cancelación <3h → 422 con mensaje y contacto del consultorio.
- [ ] CA-3: Autenticación solo por `token_cancelacion` (GATE 2026-10-11 PB-01; sin DNI+teléfono, sin "mis turnos").
**Reglas relacionadas**: RN-TU-04, RN-TU-06.

## Épica 3: Gestión recepción (staff)

### US-006 — CRUD recepción de turnos
**Como** recepción **Quiero** crear/editar/borrar turnos de cualquier paciente **Para** gestionar teléfono y mostrador.
**Criterios de aceptación**:
- [ ] CA-1: Crear con los mismos obligatorios que online + `origen=recepcion`.
- [ ] CA-2: Editar (reprogramar/cambiar duración) valida anti-solape igual que online.
- [ ] CA-3: Borrar = `cancelado` (no DELETE físico); forzar <3h exige motivo y audita.
**Reglas relacionadas**: RN-TU-02, RN-TU-03, RN-TU-04, RN-AU-02.

### US-007 — Validar datos del paciente
**Como** recepción **Quiero** ver y corregir DNI/teléfono/OS de un turno **Para** validar su validez.
**Criterios de aceptación**:
- [ ] CA-1: Ficha del turno muestra datos + historial de cambios.
- [ ] CA-2: Edición de datos escribe auditoría.
**Reglas relacionadas**: RN-PA-01, RN-PA-02, RN-AU-02.

### US-008 — Marcar asistencia
**Como** odontólogo/recepción **Quiero** marcar confirmado/atendido/ausente **Para** llevar presentismo.
**Criterios de aceptación**:
- [ ] CA-1: Solo transiciones válidas (RN-TU-07).
- [ ] CA-2: `ausente` alimenta reporte de ausentismo.
**Reglas relacionadas**: RN-TU-07.

## Épica 4: Notificaciones mail (v1)

### US-009 — Confirmación y recordatorios por mail
**Como** paciente **Quiero** recibir confirmación + recordatorios 24h/2h **Para** no olvidar mi turno.
**Criterios de aceptación**:
- [ ] CA-1: Confirmación encolada al reservar, enviada en <5 min.
- [ ] CA-2: Recordatorios solo si la anticipación lo permite; cada envío incluye link de cancelación.
- [ ] CA-3: Fallos visibles en panel recepción tras 3 reintentos; la reserva nunca se bloquea por fallo de mail.
**Reglas relacionadas**: RN-NO-01, RN-NO-02.

## Épica 5: Admin y reportes mínimos

### US-010 — Gestionar profesionales y staff
**Como** admin **Quiero** alta/baja de profesionales y usuarios staff con rol **Para** operar el consultorio.
**Criterios de aceptación**:
- [ ] CA-1: Alta con `duracion_default_min` configurable.
- [ ] CA-2: Baja = `activo=false`, conserva historial.
**Reglas relacionadas**: RN-AU-01, RN-TU-02.

### US-011 — Reporte básico de ocupación
**Como** admin/recepción **Quiero** ver ocupación y ausentismo por profesional y período **Para** detectar huecos.
**Criterios de aceptación**:
- [ ] CA-1: Tabla por profesional: turnos, atendidos, ausentes, cancelados, % ocupación.
- [ ] CA-2: Filtro por rango de fechas.
**Reglas relacionadas**: — (lectura de estados RN-TU-07).

## Explícitamente NO-US en v1 (post-v1)

- NO-US-01 WhatsApp (recordatorio con confirmar/cancelar, bot). — Puerta en 02/08.
- NO-US-02 Seña MP + política no-show con pago.
- NO-US-03 Lista de espera con oferta de huecos.
- NO-US-04 HC/odontograma/presupuestos; ficha clínica.
- NO-US-05 Validación padrón OS; facturación ARCA.

# Discovery — turnos-odontologia_cattaneo

**Fecha**: 2026-10-10 (ajuste market research: 2026-10-11)
**Fuentes investigadas**: 18 sistemas verificados (ver `discovery/market-research-odontologia-AR.md`, consulta 2026-10-10/11; solo sitios oficiales, precios, docs y reseñas; "No evidenciado" donde corresponde)

## 1. Problema que resuelve

El consultorio coordina turnos por WhatsApp/papel/planilla, lo que genera
dobles reservas y tiempo perdido confirmando manualmente cada turno.

## 2. Usuarios / roles

- **Paciente**: ve horarios libres y reserva/cancela sin llamar ni escribir.
- **Odontólogo/a**: ve sus turnos agendados para organizar sus horarios. Varios
  profesionales con agenda propia desde el día 1.
- **Recepción/Admin**: CRUD completo de turnos (crea, edita, borra) y comprueba
  los datos del cliente para validar su validez.

## 3. Casos de uso

1. Como paciente, quiero ver los horarios libres para reservar sin tener que
   llamar.
2. Como odontólogo, quiero ver mis turnos agendados para organizar mis
   horarios.
3. Como recepción, quiero crear/editar/borrar turnos y comprobar los datos del
   cliente para validar su validez.

## 4. Competidores / soluciones existentes

La competencia a reemplazar sigue siendo el proceso actual: WhatsApp +
papel/planilla. Además se investigaron 18 sistemas (informe completo en
`discovery/market-research-odontologia-AR.md`, con matriz ponderada y análisis C–D):

| Competidor | Origen | Relevancia para el proyecto | Precio / modelo |
|---|---|---|---|
| Dentalink | Chile/LatAm | Líder LatAm dental (odontograma, sobreagenda, campañas); sin ARCA/MP evidenciados | A cotizar |
| Odentix | Argentina | Dental puro AR con IA y recordatorios WA; vara local directa | Planes a cotizar |
| ClinIA | Argentina | Vara integración AR (PUCO/RENAPER/ReNaPDiS/AFIP); sin odontograma | A cotizar |
| DoctorYa | Argentina | Bot WA que reserva + ARCA + precios publicados | $9.000–$90.000/mes |
| ZynkMed | Argentina | Sitio propio + lista de espera + inbox WA | $150.000–$200.000/mes |
| MediTurn | Argentina | Bot WA 24/7, +20 obras sociales | $65.000/mes |
| Medilink / AgendaPro / dt.dental | Chile/Chile/Colombia | Referencias LatAm (clínica, agenda, marketing) | A cotizar |
| Docturno / Doctoralia | Argentina / ES-AR | Marketplaces: canal de adquisición + referencia UX, no HC | — / planes s/monto AR |
| Meducar / DarTurnos | Argentina | Turnero+HC simple / turnero con Mercado Pago (piso de precio) | — / $3.300/mes |
| Open Dental / Dentrix / Curve / NexHealth / Fresha | EE. UU./UK | Referencias internacionales (clínica full, UX, automatización); sin encaje AR | USD 199/mes → enterprise |

**Hallazgo central**: nadie ocupa la intersección "odontología pura + administración
argentina (obras sociales, ARCA, Mercado Pago)": los dentales no integran AR y los AR
integrados no tienen odontograma. Ver secciones C (estándar vs. diferencial vs. vacíos)
y D (5 demos prioritarias, 3 referencias UX, MVP) en el informe.

## 5. Funcionalidades necesarias

En orden de prioridad declarado por el usuario:

1. Gestión de recepción (crear/editar/borrar/validar turnos).
2. Agenda por profesional con vista diaria/semanal.
3. Reserva online por paciente (con DNI/teléfono/obra social obligatorios).
4. Cancelación con anticipación mínima de 3 horas.
5. Duración de turno predefinida de 30 minutos, personalizable por el personal.
6. Recordatorios automáticos por mail (v1).

## 6. Funcionalidades opcionales

- Historia clínica / ficha del paciente vinculada al turno (post-v1).

## 7. Reglas de negocio

- No se puede reservar sin DNI/teléfono; obra social requerida (campo
  obligatorio al reservar).
- No se puede cancelar un turno con menos de 3 horas de anticipación.
- Un profesional no puede tener dos turnos superpuestos.
- Duración default de 30 minutos, personalizable por el personal (recepción/
  admin puede cambiarla por turno o por profesional).

## 8. Integraciones

- **Mail**: recordatorios automáticos (v1 confirmado).
- **WhatsApp**: comunicación/recordatorios (alcance v1 vs. post-v1 a definir).
- **Sistemas de obras sociales**: alcance a definir (¿campo obligatorio o
  validación contra padrón/API?).

## 9. Restricciones

- Tiene que andar bien en celular — la mayoría de los pacientes va a reservar
  desde el teléfono, no desde una computadora (mobile-first).
- Sin stack obligatorio ni plazo rígido declarado.

## 10. Riesgos

- **Principal**: si recepción no mantiene las disponibilidades actualizadas, el
  sistema muestra horarios que en realidad no están libres → choques y dobles
  reservas.
- **Supuesto sin probar**: que la validación de obra social como campo
  obligatorio alcance sin consultar padrón externo — no está validado contra
  sistemas reales todavía. Evidencia nueva: ClinIA valida contra PUCO/RENAPER y
  DoctorYa gestiona copagos por plan; el mercado ya resolvió que se valida, no
  que se declara (ver informe C.2.5).
- **Nuevo (mercado)**: el v1 con recordatorios solo por mail queda por debajo del
  estándar (13/18 usan WhatsApp); lanzar sin WhatsApp es desventaja evidenciada.
- **Nuevo (mercado)**: opacidad de precios y cautividad de datos son quejas del
  segmento; ningún vendor AR publicita exportación (ver informe C.3.4–C.3.5).

## 11. Preguntas abiertas

- ¿Hace falta login para el paciente, o alcanza con DNI + teléfono por turno?
- ¿Validación de obra social es solo campo obligatorio o hay que consultar
  algún padrón/API? (Evidencia: ClinIA/DoctorYa validan; se recomienda validar.)
- ¿WhatsApp entra en v1 junto al mail, o el recordatorio v1 es solo mail y
  WhatsApp va después? (Evidencia: el informe recomienda WhatsApp primero, mail
  como fallback.)
- ¿Se incluye seña por Mercado Pago + lista de espera con huecos en v1 o v1.1?
  (Evidencia: DarTurnos/Fresha lo prueban como piso; ZynkMed/NexHealth la lista.)

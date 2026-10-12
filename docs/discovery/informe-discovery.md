# Informe de Discovery — Sistema de gestión de turnos y agenda para consultorios odontológicos (mercado argentino)

> **Portada**
>
> | Campo | Detalle |
> |---|---|
> | **Título** | Informe de Discovery: investigación de mercado de sistemas odontológicos con gestión de turnos (Argentina y región) |
> | **Materia** | Metodología I — Trabajo de Integración: del Discovery al primer Change (SDD + Active Stack) |
> | **Integrantes** | A completar por el equipo (no consta en el repositorio) |
> | **Fecha de consulta de fuentes originales** | 2026-10-10 / 2026-10-11 |
> | **Fecha de verificación de fuentes y edición de este informe** | 2026-10-12 |
> | **Fuente histórica** | `discovery/market-research-odontologia-AR.md` (247 líneas) + `discovery/discovery.md` (checklist de 11 puntos). La carpeta `discovery/` se conserva como fuente histórica; este informe es el entregable de la Etapa 2 en la ubicación exigida por la consigna. |
> | **Stack del proyecto** | FastAPI + React + Postgres (ver `knowledge-base/`, `AGENTS.md`, `CHANGES.md`) |
>
> **Criterio metodológico** (heredado del market-research, sin cambios): solo fuentes verificables
> (sitios oficiales, páginas de precios, documentación pública, centros de ayuda, marketplaces y
> reseñas verificadas). Cada afirmación lleva su URL. Lo no demostrado públicamente se consigna como
> **"No evidenciado"**. Se distingue siempre entre **funcionalidad comprobada** (visible en producto,
> docs o demo oficial) y **afirmación comercial** (texto de marketing sin evidencia pública).
> Las correcciones aplicadas tras la verificación del 2026-10-12 se marcan con
> **[Ajuste verificación 2026-10-12]** y se detallan en la sección 7.

---

## Resumen ejecutivo

Se investigaron **18 sistemas** con gestión de turnos y agenda (Argentina, Latinoamérica y referencias
internacionales) a partir de fuentes oficiales consultadas el 2026-10-10/11, con verificación personal
de 6 fuentes el 2026-10-12 (ver sección 7). El checklist de 11 puntos de `discovery-research`
(problema, usuarios, casos de uso, competidores, funcionalidades necesarias/opcionales, reglas de
negocio, integraciones, restricciones, riesgos y preguntas abiertas) se conserva en
`docs/discovery/checklist-11-puntos.md` (copia fiel de `discovery/discovery.md`).

**Principales hallazgos.** (1) Nadie ocupa la intersección **"odontología pura + administración
argentina"**: los dentales puros (Dentalink, Odentix) no integran obras sociales/ARCA/Mercado Pago, y
los SaaS argentinos integrados (ClinIA, DoctorYa, ZynkMed) no tienen odontograma. Ese es el hueco de
producto. (2) El estándar de mercado incluye agenda por profesional, reserva online 24/7,
recordatorios automáticos (**13/18 usan WhatsApp**) y prevención de solapamientos: un v1 con
recordatorios **solo por mail queda por debajo del estándar**. (3) La validación de obra social
contra padrón (ClinIA: RENAPER+PUCO; DoctorYa: copagos por plan) ya es práctica evidenciada, no una
hipótesis. (4) La opacidad de precios y la cautividad de datos son quejas del segmento: publicar
precios en ARS y garantizar exportación es diferencial comercial.

**MVP recomendado (sección D.3).** Imprescindibles v1: agenda multi-profesional con duraciones
variables y anti-solape; reserva online sin login (DNI/teléfono/obra social obligatorios);
**recordatorios por WhatsApp** con confirmar/cancelar (mail como fallback, elevando el Discovery
original "solo mail"); cancelación con antelación configurable (3 h); CRUD de recepción con bloqueos
y sobreturnos; ficha básica con archivos; roles y permisos; reportes básicos; mobile-first. Para
v1/v1.1: verificación de cobertura, lista de espera con huecos, seña por Mercado Pago, exportación
garantizada y declaración Ley 25.326. Post-v1: odontograma full, facturación ARCA/liquidaciones,
recupero de inactivos y chatbot.

**Verificación (2026-10-12).** Se abrieron y comprobaron 6 fuentes de 5 tipos (sitio oficial, página
de precios, centro de ayuda, documentación de precios open-source, página de producto con precios
AR). Veredicto: 3 confirmaciones plenas y 3 correcciones aplicadas (detalladas en la sección 7),
ninguna de las cuales invalida las conclusiones: las refuerzan (Mercado Pago y odontograma de
DoctorYa/ZynkMed quedaron mejor evidenciados; los precios de Fresha se actualizaron a ARS vigentes).

---

## A. Tabla comparativa (18 sistemas, ordenados por relevancia para Argentina)

Leyenda de columnas: **Origen** (país de la empresa) · **Seg.** (segmento objetivo) ·
**Mod.** (modalidad) · **Precios publicados** (sí/no + valores) · **WhatsApp** · **Odonto**
(funcionalidad odontológica clínica: odontograma, ficha, presupuestos).

| # | Sistema / Empresa / URL | Origen | Seg. | Mod. | Agenda y turnos (comprobado) | Turnos digitales / automatización | Odonto clínica | Admin / cobros / facturación | Integraciones locales AR | Precios publicados | Adopción evidenciada |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Dentalink** — Engenis SpA — https://www.softwaredentalink.com/ | Chile | Consultorio, clínica, cadena | SaaS nube | Vista agenda con estados, sobreagenda paralela, tiempos por odontólogo, reprogramación individual/masiva, prevención de sobreagendamiento (comprobado en página de Agenda) | Reserva online 24/7, link por WhatsApp/Instagram/web, recordatorios WhatsApp y email, confirmación/reprogramación, campañas de recupero, telemedicina (comprobado) | Ficha clínica digital, odontograma y periodontograma interactivos, ortodoncia, estética facial, imágenes/documentos, firma digital, IA (notas por voz, análisis RX, resumen clínico) (comprobado) | Pagos presenciales y online, gestión de convenios, reportes por área (comprobado). Mercado Pago / AFIP: **No evidenciado** | WhatsApp (comprobado). Google Calendar: No evidenciado. API pública: No evidenciado en sitio LatAm | No — "Solicita tu cotización" | Afirmación comercial: +15.000 clientes, +12M pacientes, +45M citas/año, +20 países. Reseñas verificadas independientes: No evidenciado. **[Ajuste verificación 2026-10-12: home verificado muestra "+15.000 clínicas", "+20 países", "+100K profesionales", "+16 años"; las cifras de pacientes/citas no visibles en home — se mantienen como afirmación comercial. Ver F-1.]** |
| 2 | **Odentix** — Odentix (AR) — https://odentix.framer.website/ | Argentina | Independiente, consultorio, clínica | SaaS nube | Agenda día/semana/mes, reprogramación, turno rápido, disponibilidad en tiempo real (comprobado) | Recordatorios automáticos WhatsApp/email/SMS, reserva online (comprobado). Lista de espera: No evidenciado | Historia clínica + odontograma, tratamientos y presupuestos, dictado por voz, resumen IA de consulta, 30–100 MB archivos (comprobado) | Pagos y presupuestos, seguimiento económico, indicadores (comprobado). Facturación AFIP / Mercado Pago: No evidenciado | WhatsApp/email/SMS (comprobado). Mercado Pago, AFIP, API: No evidenciado | Parcial — planes Starter / Starter IA / Full IA "a cotizar", sin montos | Afirmación comercial: 4.9/5 "recomendado por odontólogos" (sin fuente de reseña citada). N.º de clientes: No evidenciado |
| 3 | **ClinIA** — ClinIA (AR) — https://www.clinia.com.ar/software-para-clinicas | Argentina | Clínica, centro médico, sanatorio | SaaS nube | Agenda por profesional con turnero web, recepción y sala de espera (comprobado) | Reserva por web/WhatsApp/app paciente, recordatorios WhatsApp/email/SMS (comprobado). Lista de espera: No evidenciado | Historia clínica electrónica con firma digital, documentos/estudios (comprobado). Odontograma: **No evidenciado** (producto médico general) | Obras sociales/prepagas/PAMI con nomenclador, facturación AFIP, caja (comprobado). Mercado Pago: No evidenciado | RENAPER + PUCO (verificación identidad y cobertura), ReNaPDiS (recetario n.º 248, HL7 FHIR), AFIP, WhatsApp (comprobado) | No — demo a cotizar | Afirmación comercial: +500 centros, +1,2M pacientes. Reseñas verificadas: No evidenciado |
| 4 | **DoctorYa** — DoctorYa (AR) — https://doctorya.com.ar/ | Argentina | Independiente, consultorio, clínica/sanatorio | SaaS nube (100% navegador) | Agenda por profesional y sede, programar/reprogramar/cancelar, vista del día con estados (comprobado) | Reserva online 24/7 + asistente conversacional que reserva por chat, recordatorios WhatsApp con CONFIRMAR/CANCELAR y actualización automática (comprobado). Lista de espera: No evidenciado | Ficha del paciente con evoluciones, estudios, archivos, odontogramas (mencionado en sitio; profundidad odontológica: No evidenciado en demo pública) **[Ajuste verificación 2026-10-12: el centro de ayuda tiene artículo dedicado "Ficha Clínica, archivos adjuntos y odontograma" — odontograma comprobado a nivel de centro de ayuda. Ver F-6.]** | Obras sociales y copagos por profesional, facturación electrónica ARCA válida Monotributo/RI (comprobado). Mercado Pago: **[Ajuste verificación 2026-10-12: home verificado 2026-10-12 muestra "Pagos con Mercado Pago" — mención comprobada; detalle técnico de la integración: No evidenciado. Ver F-2.]** | WhatsApp, ARCA (comprobado). Google Calendar, API: No evidenciado | **Sí** — Argenti $9.000/mes (1 agenda), Aurum $25.000/mes (hasta 5), plan institucional $90.000/mes; primer mes gratis **[Ajuste verificación 2026-10-12: planes y montos confirmados en home 2026-10-12; el tercer plan aparece rotulado "Argenti" en el sitio (posible error del vendor) — se mantiene "institucional" como interpretación. Ver F-2.]** | Testimonios en sitio (sin plataforma de reseña citada). N.º de clientes: No evidenciado |
| 5 | **ZynkMed** — ZynkMed (AR) — https://zynkmed.com.ar/ | Argentina | Consultorio, centro médico | SaaS nube + sitio web propio por consultorio | Vista diaria/semanal por profesional, sobreturnos, bloqueos (comprobado en demo visible) | Reserva online 24/7, WhatsApp automático + inbox, lista de espera con oferta de huecos, solicitudes online (comprobado) | Historia clínica con evoluciones, antecedentes, laboratorio en tabla, adjuntos, dictado por voz, recetas y certificados (comprobado). Odontograma: No evidenciado (médico general) | Caja y movimientos, cobro online, informes, obras sociales (comprobado). Mercado Pago: **[Ajuste verificación 2026-10-12: sitio verificado 2026-10-12 — "Cobro online… con Mercado Pago. Cada profesional vincula su propia cuenta de Mercado Pago" — comprobado; era "parcial/no verificada" en la versión anterior. Ver F-5.]** | WhatsApp (comprobado, API oficial declarada). AFIP/ARCA, API: No evidenciado | **Sí** — base hasta 5 prof. $150.000/mes, 6–10 $200.000/mes, +10 a medida; HC +$15.000 (módulo) **[verificado 2026-10-12, sin cambios. Ver F-5.]** | Casos (Consultorios Alberti) mostrados como demo, no como caso de éxito cuantificado. Reseñas: No evidenciado |
| 6 | **MediTurn** — DSL Sistemas (AR) — https://mediturn.com.ar/ | Argentina | Consultorio, clínica multi-sede | SaaS nube + bot WhatsApp + IA | Agenda en tiempo real con detección de conflictos y horarios alternativos, multi-sede (comprobado) | Reserva por agente IA WhatsApp 24/7, confirmación al reservar, recordatorio 24 h, aviso de cancelación (comprobado). Reprogramación/lista de espera: No evidenciado | Historial clínico digital con evoluciones y adjuntos (comprobado). Odontograma/periodontograma: No evidenciado | +20 obras sociales (OSDE, PAMI, Swiss Medical, Medifé, IOMA), caja (parcial). Facturación AFIP / Mercado Pago: No evidenciado | WhatsApp IA (comprobado). Mercado Pago, AFIP, API: No evidenciado | **Sí** — Premium $65.000/mes, turnos ilimitados, 7 días gratis (precios sin IVA) | Afirmación comercial: +50 consultorios, +10.000 pacientes. Reseñas verificadas: No evidenciado |
| 7 | **Medilink** — Medilink (CL) — https://www.softwaremedilink.com/ | Chile | Consultorio, clínica, policlínica | SaaS nube | Agenda por profesional/servicio/sucursal/box, reserva online 24/7, recordatorios automáticos (comprobado) | Reserva online, confirmaciones automáticas, campañas de reagendamiento, telemedicina (comprobado). Chatbot WhatsApp: No evidenciado (integraciones listadas: Google Calendar, Analytics, Meta Pixel, BSale, Kame, Nubox) | Ficha clínica personalizable por especialidad, evoluciones, recetas, documentos (comprobado). Odontograma: No evidenciado (médico general) | Flujo de caja en tiempo real, pagos anticipados con link, firma electrónica, +80 reportes, remuneraciones (comprobado). AFIP/Mercado Pago: No evidenciado | Google Calendar (comprobado). WhatsApp Business API, AFIP, Mercado Pago: No evidenciado | No — "Solicita tu asesoría" | Afirmación comercial: +12.000 clientes, +60.000 usuarios, 42M citas, +20 países. Reseñas verificadas: No evidenciado |
| 8 | **AgendaPro** — AgendaPro (CL) — https://agendapro.com/ | Chile | Clínica, consultorio, estética/bienestar | SaaS nube + marketplace | Agenda inteligente, reservas por día/hora/sede/profesional, actualización automática (comprobado) | Link de reserva (web, redes, WhatsApp, QR), reserva 24/7, recordatorios email/SMS/WhatsApp configurables, marketplace (comprobado). Lista de espera: parcial (mencionada en vertical estética) | Ficha digital del paciente con exámenes e imágenes, seguimiento de sesiones (comprobado). Odontograma: No evidenciado | Caja en tiempo real, comisiones, inventario, POS y pago online, facturación electrónica "según país" (afirmación comercial; detalle AR: No evidenciado) | WhatsApp/SMS/email (comprobado). Mercado Pago, AFIP, API pública: No evidenciado | Parcial — "ver precios" por país, sin montos AR publicados | Afirmación comercial: +80.000 profesionales, +100M citas, +49% ingresos año 1. Reseñas: SoftwareAdvice (ficha existente, puntaje no relevado acá) |
| 9 | **dt.dental** — dt.dental (CO) — https://dtdental.co/ | Colombia | Consultorio y clínica odontológica | SaaS nube | Agenda y gestión de citas automatizada (comprobado). Multisillón/bloqueos: No evidenciado | Agendamiento online/demo, recordatorios (mencionados; canal: No evidenciado) | Historia clínica digital con odontograma interactivo, inventarios, reportes (comprobado). Periodontograma/imagenología: No evidenciado | Facturación electrónica DIAN (Colombia) + RIPS Res. 2275/2023, inventarios (comprobado). AFIP/Mercado Pago: No evidenciado (operación CO) | Cumplimiento normativo CO (comprobado). Integraciones AR: No evidenciado | No — demo a cotizar | Afirmación comercial: +10.000 profesionales, 9 países LatAm, +4M citas, +1M HC. Premios (Mana Tech Miami) mencionados. Reseñas verificadas: No evidenciado |
| 10 | **Docturno** — Docturno (AR) — https://www.docturno.com/ | Argentina | Grupo médico, consultorio, paciente buscador | Marketplace + agenda (nube) | Agenda por profesional con horarios y coberturas por plan (comprobado en fichas públicas) | Reserva online por perfil público, cuenta paciente con historial (comprobado). Recordatorios/reprogramación/lista de espera: No evidenciado | Directorio con perfiles; ficha clínica: No evidenciado | Coberturas y planes por obra social/prepaga visibles (comprobado). Caja/cobros/facturación: No evidenciado | WhatsApp de contacto por perfil (comprobado). API, Mercado Pago, AFIP: No evidenciado | No — "Planes" mencionados sin montos públicos | Empresa fundada 2015 (Tracxn). Cobertura: red de centros AR (evidencia: fichas activas). Reseñas de producto: No evidenciado |
| 11 | **Doctoralia** — Docplanner / Doctoralia Internet SL (ES) — https://www.doctoraliar.com/ · https://pro.doctoralia.com/ar/agenda-doctoralia-para-especialistas | España (opera AR) | Independiente, consultorio, clínica | Marketplace + SaaS agenda | Agenda unificada online, personalización desde celular (comprobado) | Reserva 24/7 multicanal (perfil, web, Google, redes), recordatorios SMS/email/WhatsApp y push, lista de espera inteligente (plan VIP), reprogramación (70% según marketing — afirmación comercial), videoconsulta (comprobado en planes) | Expediente/ficha clínica digital (plan Plus, comprobado). Odontograma: No evidenciado | Campañas email/SMS, estadísticas; caja/cobros/facturación AR: No evidenciado | Google, redes, widgets omnicanal (comprobado). Mercado Pago, AFIP, API: No evidenciado | Parcial — AR sin montos públicos (referencia CL: Starter $59.000 CLP/mes aprox. — ver https://pro.doctoralia.cl/precios) | Afirmación comercial: 110.000 profesionales en AR, −65% ausentismo, +2 h/día ahorradas. Reseñas: opiniones de pacientes por perfil (verificabilidad parcial, moderación declarada) |
| 12 | **Meducar** — Meducar (AR) — http://meducar.com/ | Argentina | Consultorio, centro de salud | SaaS nube + app móvil | Gestión de turnos multi-profesional (mencionado; vistas/duración variable: No evidenciado) | Sitio web de turnos online, avisos y recordatorios WhatsApp y email (comprobado en sitio + testimonios) | Historia clínica completa, imágenes/documentos, prescripciones, prácticas por especialidad (comprobado). Odontograma: No evidenciado | Control de caja, estadísticas (comprobado). Facturación AFIP / Mercado Pago: No evidenciado | WhatsApp, app móvil (comprobado). API, Mercado Pago, AFIP: No evidenciado | No — "Crea tu cuenta" sin montos | Testimonios con matrícula de médicas/os AR (verificabilidad parcial). N.º de clientes: No evidenciado |
| 13 | **DarTurnos** — DarTurnos (AR, Bahía Blanca) — https://darturnos.com/ | Argentina | Consultorio, servicios por turno | SaaS turnero (nube) | Turneros configurables con duración, rangos y días (comprobado) | Reserva 24/7 PC/tablet/celular, recordatorios WhatsApp (módulo pago), pantalla llamadora (módulo pago) (comprobado) | No — turnero genérico, sin ficha clínica (comprobado por ausencia) | Cobro de turnos con Mercado Pago (módulo pago, comprobado). Facturación AFIP: No evidenciado | Mercado Pago, WhatsApp (módulos pagos, comprobado) | **Sí** — 1 turnero $3.300/mes ($33.000/año); mensajes WhatsApp desde $6.000/50; prueba 30 días gratis | Dirección y teléfono AR publicados. N.º de clientes / reseñas: No evidenciado |
| 14 | **Open Dental** — Open Dental Software (US) — https://www.opendental.com/ · https://www.opendental.com/site/fees.html | EE. UU. | Consultorio, clínica, facultad | Instalación local (.NET) u Open Dental Cloud; código abierto (GPL-2.0, repositorio público) | Agenda con patrones de tiempo por procedimiento, multi-sede (comprobado en manual) | Web Sched (reserva online), portal del paciente, recordatorios/mensajería, texting integrado, eClipboard (comprobado; requiere eServices pagos) | Odontograma gráfico 3D, periodontograma, ortodoncia, planes de tratamiento, imágenes, eRx (comprobado en manual) | Ledger, planes de pago, seguros (modelo EE. UU.), reportes (comprobado). AFIP/obras sociales AR: No evidenciado (no aplica) | API/desarrollo propio (comprobado: docs para developers). WhatsApp, Mercado Pago, AFIP: No evidenciado | **Sí** — licencia+soporte EE. UU. USD 199/mes/consultorio (hasta 3 prestadores); eServices y ODTouch/ODMobile adicionales; facultades gratis **[verificado 2026-10-12 en página de fees, sin cambios. Ver F-4.]** | Empresa desde 2003, ~222 empleados, foros y comunidad activos (evidencia: manual público, webinars, newsletter). Reseñas: Capterra/G2 (no relevadas acá) |
| 15 | **Dentrix** — Henry Schein One (US) — https://www.dentrix.com/ | EE. UU. | Consultorio, clínica, cadena/DSO | Instalación local + Dentrix Ascend (nube) | Agenda, multi-sede, flujos por rol (comprobado a nivel marketing; detalle técnico en demo) | Patient engagement, recordatorios, reserva online (línea Ascend; comprobado a nivel marketing) | Odontograma, imagen (Smart Image), planes de tratamiento, analítica (Practice Advisor) (comprobado a nivel marketing) | Facturación, seguros, cobros, analítica (modelo EE. UU., comprobado a nivel marketing). AR: No evidenciado | Integraciones con hardware/imagen del ecosistema Henry Schein (comprobado). WhatsApp, Mercado Pago, AFIP, API pública: No evidenciado | No — demo a cotizar | Afirmación comercial: "líder mundial", 30+ años, 35.000+ clientes (línea Dentrix+Dentally CA). Premio Townie Choice 2025 (declarado). Reseñas: Capterra (no relevadas acá) |
| 16 | **Curve Dental** — Curve Dental (US) — https://www.curvedental.com/ | EE. UU. | Consultorio, clínica multi-sede | SaaS nube con IA | Agenda conectada multi-sede (comprobado a nivel marketing) | Reserva online 24/7 con reglas, formularios, engagement (comprobado a nivel marketing) | Odontograma, imágenes con IA, planes, eRx (comprobado a nivel marketing) | Facturación, seguros, pagos, reportes multi-sede (comprobado a nivel marketing) | Colaboración/portal (marketing). WhatsApp, Mercado Pago, AFIP: No evidenciado | No oficial — referencia Capterra: desde ~USD 698/mes (ver https://www.capterra.com/compare/98688-176206/Curve-Dental-Hero-vs-CareStack) | Capterra 4.4 (285 reseñas) (verificada en comparador). Casos: migraciones desde Dentrix/Open Dental (declarado) |
| 17 | **NexHealth** — NexHealth (US) — https://www.nexhealth.com/doctors · https://try.nexhealth.com/for-dental | EE. UU. | Clínica/cadena (capa de experiencia del paciente) | SaaS nube (se monta sobre el PMS existente) | Sincronización bidireccional con el PMS, importación de calendarios (comprobado) | Reserva online (Google incluida), recordatorios, reprogramación, lista de espera que rellena huecos, formularios digitales, mensajería (comprobado). 73% de reservas fuera de horario (afirmación comercial) | No — no es HC odontológica; verifica seguros y gestiona formularios (comprobado) | Pagos y planes de pago sincronizados al ledger, verificación de seguros (modelo EE. UU., comprobado) | +60 integraciones PMS (Dentrix, Eaglesoft, Open Dental, Curve, etc. — comprobado en lista pública). WhatsApp, Mercado Pago, AFIP: No evidenciado | No — demo a cotizar | Casos con métricas (Bastida Dental −USD 2k/mes en fees, Perfect Smile +35 reservas Google) — publicados por el vendor, verificabilidad parcial |
| 18 | **Fresha** — Fresha.com SV Ltd (UK) — https://www.fresha.com/pricing · https://www.fresha.com/business | Reino Unido | Independiente, salón/clínica estética/bienestar | SaaS nube + marketplace | Calendario multi-staff, citas recurrentes, lista de espera (comprobado) | Reserva 24/7 (marketplace, link, Google, redes), recordatorios email/SMS/WhatsApp, pagos anticipados y anti-ausentismo (comprobado). Chatbot: No evidenciado | Formularios de consulta (comprobado). Odontograma/HC: no (producto belleza, no clínico) | POS, inventario, comisiones, reportes, pagos online/presenciales (comprobado). Facturación AR: No evidenciado | Google/ redes / Xero (comprobado). Mercado Pago, AFIP, API pública: No evidenciado | **Sí — [Ajuste verificación 2026-10-12: página de precios verificada 2026-10-12, geolocalizada AR: Independent ARS 8.000/mes; Team ARS 5.300/miembro/mes; prueba 7 días; WhatsApp ARS 180–375 (tras 20 gratis); marketplace clientes nuevos "Free" en el comparador actual. Los valores USD 19,95 / 14,95, la comisión del 20% y el procesamiento 2,29–2,79% + USD 0,20 de la versión anterior quedan como No evidenciado en la página actual. Ver F-3.]** | 130.000+ negocios, 450.000+ profesionales, 1B+ reservas (vendor). Capterra 4.8 (reseña Pabau 2026-08-25, verificabilidad parcial) |

**Nota sobre Consulmed** (https://www.consulmed.com.ar/): empresa argentina de prestación,
administración y financiamiento de servicios odontológicos ("líder en odontología en
Argentina"), no un software SaaS contratable: se la excluye de la tabla por no ser
competidor de producto, pero se la registra como actor del ecosistema (potencial validador
de nomencladores y convenios).

**Fuentes consultadas** (todas con fecha 2026-10-10/11): las 18 URLs oficiales de la tabla
más páginas de precios/funcionalidad citadas en las celdas (Dentalink agenda y agendamiento
online; Doctoralia PRO AR y precios CL; Open Dental fees; Capterra Curve vs CareStack;
Fresha pricing; reseña Pabau sobre Fresha 2026-08-25; ficha Tracxn Docturno; ClinIA;
ZynkMed; MediTurn; DoctorYa; Odentix; Medilink; AgendaPro; dt.dental; Meducar; DarTurnos;
Docturno; Dentrix; Curve; NexHealth; DEXIS https://dexis.com/es-es como referencia de
imagenología — excluido de la tabla por no ser PMS).

---

## B. Matriz de puntuación (0–5 por dimensión, con pesos)

**Nota metodológica.** Pesos: Turnos y automatización 25% · Clínica odontológica 20% ·
Integraciones locales y WhatsApp 15% · Administración, cobros y facturación 15% · Experiencia del
paciente 10% · Seguridad, exportación y trazabilidad 10% · Precio y facilidad de adopción 5%.
Puntaje total ponderado sobre 5. Criterio: 5 = evidenciado y sobresaliente; 3 = evidenciado
básico; 1 = ausente o no odontológico; 0 = sin evidencia de la dimensión. **"No evidenciado"
resta (no se presume)**: ninguna celda se completó por deducción; toda celda sin respaldo público
dice "No evidenciado" en la Tabla A y puntúa 0–1 en su dimensión. La distinción
comprobado / afirmación comercial de la Tabla A se traslada acá: el marketing sin evidencia no suma.

> **[Ajuste verificación 2026-10-12]** La fila "CareStack (ref. int.)" proviene de la fuente
> histórica sin URL ni entrada en la Tabla A: se mantiene visible pero marcada como referencia sin
> fuente (No evidenciado en Tabla A) y **no debe computarse** como competidor relevado. Las
> correcciones F-2/F-3/F-5 no alteran los puntajes (elevan evidencia puntual ya contenida en el
> rango de la celda), salvo Fresha-precio que se mantiene por tratarse de la misma banda accesible.

| # | Sistema | Tur/Aut 25% | Clínica 20% | Integ 15% | Admin 15% | Exp.Pac 10% | Seg/Exp 10% | Precio 5% | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Dentalink | 5 | 5 | 3 | 4 | 4 | 4 | 2 | **4,20** |
| 2 | ClinIA | 4 | 3 | 5 | 4 | 4 | 4 | 2 | **3,85** |
| 3 | CareStack (ref. int. — **[sin fuente en Tabla A: No evidenciado; fila de referencia, no competidor relevado]**) | 4 | 5 | 1 | 5 | 4 | 4 | 1 | **3,75** |
| 4 | DoctorYa | 4 | 2 | 5 | 4 | 4 | 3 | 5 | **3,70** |
| 5 | ZynkMed | 4 | 3 | 4 | 4 | 4 | 3 | 3 | **3,65** |
| 6 | Odentix | 4 | 4 | 3 | 3 | 4 | 3 | 4 | **3,60** |
| 7 | Curve (ref. int.) | 4 | 5 | 1 | 4 | 4 | 4 | 1 | **3,60** |
| 8 | MediTurn | 5 | 2 | 4 | 3 | 4 | 2 | 4 | **3,50** |
| 9 | dt.dental | 4 | 4 | 2 | 4 | 3 | 3 | 3 | **3,45** |
| 10 | Dentrix (ref. int.) | 3 | 5 | 1 | 5 | 3 | 4 | 1 | **3,40** |
| 11 | Medilink | 4 | 3 | 2 | 4 | 4 | 3 | 2 | **3,30** |
| 12 | Open Dental (ref. int.) | 3 | 5 | 1 | 4 | 2 | 4 | 3 | **3,25** |
| 13 | NexHealth (ref. int.) | 5 | 1 | 2 | 2 | 5 | 4 | 1 | **3,00** |
| 14 | AgendaPro | 4 | 1 | 2 | 4 | 4 | 3 | 3 | **2,95** |
| 15 | Meducar | 3 | 3 | 3 | 2 | 3 | 2 | 4 | **2,80** |
| 16 | Docturno | 3 | 1 | 4 | 1 | 3 | 2 | 4 | **2,40** |
| 17 | Fresha (ref. UX) | 4 | 0 | 1 | 3 | 4 | 2 | 4 | **2,40** |
| 18 | DarTurnos | 3 | 1 | 3 | 2 | 3 | 1 | 5 | **2,35** |
| 19 | Doctoralia | 3 | 1 | 2 | 1 | 5 | 3 | 3 | **2,35** |

Lectura crítica: los internacionales puntúan alto en clínica pero colapsan en
"Integraciones locales" (nadie integra ARCA/obras sociales/Mercado Pago ni WhatsApp como
canal principal), por eso pierden contra locales aun con mejor ficha clínica. Los
marketplaces (Docturno, Doctoralia, Fresha) puntúan alto en experiencia del paciente pero
bajo en clínica y administración: no son competidores directos del producto a construir,
son **canal de adquisición** y **referencia de UX**. DarTurnos lidera en precio pero es
solo turnero sin clínica: fija el **piso de precio** del mercado, no el techo de valor.

---

## C. Análisis competitivo

### C.1. Funcionalidades que ya son estándar de mercado (el MVP debe incluirlas o explicar por qué no)

1. **Agenda por profesional con vista diaria/semanal** — presente en los 18 (salvo matices
   en marketplaces). Sin esto no hay producto.
2. **Duración variable por prestación/profesional** — Dentalink (tiempos por odontólogo),
   AgendaPro, Fresha, Open Dental (patrones por procedimiento) lo tienen evidenciado. El
   Discovery v1 ya lo prevé (30' default personalizable): validado por el mercado.
3. **Reserva online 24/7 con link compartible** (web, redes, WhatsApp) — estándar en 14/18.
4. **Recordatorios automáticos** (email como mínimo; WhatsApp como norma regional) —
   estándar en 13/18. El v1 del proyecto prevé solo mail: el mercado exige WhatsApp desde
   el día 1 (ver C.3).
5. **Confirmación / cancelación / reprogramación por el paciente** — estándar en 12/18.
6. **Prevención de solapamientos** — evidenciada en Dentalink, MediTurn, AgendaPro
   **[Ajuste verificación 2026-10-12: la mención a "MediFlow" de la fuente histórica no tiene
   URL ni entrada en la Tabla A — No evidenciado; se retira de la enumeración]**.
   Regla de negocio ya confirmada en Discovery: validada.
7. **Ficha del paciente con archivos/estudios** — estándar en 13/18 (aunque el odontograma
   full solo en dentales puros).
8. **Roles y permisos** (recepción / profesional / admin) — estándar declarado en
   Dentalink, ZynkMed, Open Dental, Dentrix, Fresha.
9. **Reportes y métricas básicas** — estándar en 12/18.

### C.2. Funcionalidades diferenciadoras reales (pocos las tienen evidenciadas)

1. **Odontograma + periodontograma interactivos con planes de tratamiento y presupuestos**
   — solo Dentalink, Odentix, dt.dental, Open Dental, Dentrix, Curve, CareStack. Ningún
   SaaS médico-generalista argentino lo tiene: es **el** diferencial clínico.
   **[Ajuste verificación 2026-10-12: "CareStack" es referencia sin fuente en Tabla A —
   No evidenciado como competidor relevado; el diferencial se sostiene con los 6 restantes.]**
2. **Recupero de pacientes inactivos / controles periódicos automatizados** — Dentalink
   (campañas), Medilink (campañas). En AR local: casi nadie lo tiene evidenciado.
   **[Ajuste verificación 2026-10-12: la mención a "Dentipilot sobre Dentalink (externo)" de la
   fuente histórica no tiene URL citada — No evidenciado; se retira.]**
3. **Lista de espera que rellena huecos automáticamente** — ZynkMed (oferta de huecos),
   NexHealth, Doctoralia VIP, Fresha. Diferencial operativo directo contra ausentismo.
4. **Asistente conversacional / chatbot que reserva** — DoctorYa, MediTurn (bot WA 24/7),
   NexHealth. Diferencial de conversión + accesibilidad para pacientes poco digitales.
5. **Verificación contra padrones oficiales** — ClinIA (RENAPER + PUCO) es el único con
   evidencia. Responde exactamente la pregunta abierta del Discovery sobre validación de
   obra social: **el mercado ya resolvió que se valida contra padrón**, no con campo libre.
6. **Firma digital / documentos con validez** — Dentalink, ClinIA, Medilink, Odentix
   (planes superiores). Poco común en el segmento chico: diferencial de seriedad.
7. **Dictado por voz / IA clínica** (notas, resumen, análisis RX) — Dentalink, Odentix,
   ZynkMed, Curve. **[Ajuste verificación 2026-10-12: la mención a "tab32" de la fuente
   histórica no tiene URL ni entrada en la Tabla A — No evidenciado; se retira.]**
   Tendencia 2025–2026, aún no estándar: ventana de diferenciación.
8. **Sitio web propio del consultorio integrado** — ZynkMed (dominio propio),
   AgendaPro (web personalizable), DoctorYa (perfil web). Diferencial de adopción en
   consultorios sin web.

### C.3. Vacíos frecuentes del mercado argentino

1. **WhatsApp Business API real vs. "WhatsApp" declamado**: casi todos dicen "WhatsApp",
   pero pocos evidencian API oficial, plantillas, confirmación con respuesta que actualiza
   la agenda (solo DoctorYa y ZynkMed lo muestran operando; el resto: No evidenciado el
   mecanismo). Vacío = hacerlo bien y mostrarlo.
2. **Obras sociales y prepagas como ciudadano de primera**: solo ClinIA (PUCO +
   nomenclador + AFIP) y DoctorYa (copagos por profesional) lo tratan en serio; Docturno
   lo muestra como dato del perfil, no como gestión. Ningún dental puro AR integra
   facturación de obras sociales. **Es el vacío más grande para odontología AR.**
3. **Precios publicados en ARS**: la mayoría cotiza a pedido (Dentalink, Medilink,
   ClinIA, Odentix). Solo DoctorYa, ZynkMed, MediTurn, DarTurnos publican. La opacidad
   es una queja clásica del segmento chico: publicar precios es diferencial comercial.
4. **Cumplimiento normativo AR declarado con especificidad**: casi nadie declara Ley
   25.326 de Protección de Datos Personales, trazabilidad/auditoría ni política de
   respaldo con detalle (solo menciones genéricas de "cifrado/backups"). Quien lo declare
   con especificidad gana confianza institucional.
5. **Exportación de datos / no-cautividad**: ningún vendor AR la publicita. Open Dental
   (código abierto) es la contracara. Garantizar exportación es diferencial anti-cautiverio.
6. **Odontología pura + administración AR en un solo producto**: los dentales puros
   (Dentalink, Odentix) no integran ARCA/obras sociales; los AR integrados (ClinIA,
   DoctorYa, ZynkMed) no tienen odontograma. **Nadie ocupa la intersección.** Ese es el
   hueco donde debe pararse el producto.
7. **Cancelación con política configurable y seña**: DarTurnos cobra turnos con Mercado
   Pago y Fresha cobra no-shows; pero ningún AR dental combina seña + cancelación con
   antelación configurable + lista de espera. El Discovery (cancelación 3 h) puede
   endurecerse con seña: oportunidad.

### C.4. Oportunidades de innovación para un nuevo sistema

1. **"Dental AR nativo"**: odontograma + presupuestos/planes + obras sociales AR +
   ARCA + Mercado Pago en un solo SaaS simple. Hoy no existe evidenciado.
2. **WhatsApp primero, mail después**: invertir la pila del v1 (recordatorio WA con
   confirmar/cancelar que actualiza la agenda; mail como fallback). Es lo que el uso real
   argentino pide y lo que casi nadie hace bien.
3. **Validación de cobertura en la reserva**: padrón (PUCO donde aplique a odontología)
   o al menos verificación de formato + copago visible por plan, como DoctorYa/ClinIA.
   Convierte la pregunta abierta del Discovery en feature.
4. **Recupero automático de inactivos + controles periódicos** (limpieza semestral):
   tomar el playbook de Dentalink **[Ajuste verificación 2026-10-12: la mención a "Medec" de la
   fuente histórica no tiene URL citada — No evidenciado; se retira]** y traerlo al segmento
   chico a precio AR.
5. **Transparencia radical**: precios en ARS publicados, exportación garantizada,
   cumplimiento Ley 25.326 declarado. Posicionamiento anti-incumbente.
6. **Adopción en minutos**: onboarding sin capacitación (Fresha/AgendaPro como vara),
   sitio/link de reserva propio, prueba gratuita con datos de ejemplo odontológicos.

---

## D. Recomendación final

### D.1. Cinco competidores prioritarios para analizar mediante demo

1. **Dentalink** (https://www.softwaredentalink.com/) — el líder LatAm a destronar en
   clínica; demo para relevar odontograma, sobreagenda, campañas y su modelo de planes.
2. **Odentix** (https://odentix.framer.website/) — el competidor AR más parecido al
   producto objetivo (dental puro + IA + recordatorios); demo para medir vara local real.
3. **ClinIA** (https://www.clinia.com.ar/software-para-clinicas) — la vara de integración
   AR (PUCO/RENAPER/ReNaPDiS/AFIP); demo para copiar el circuito recepción→facturación.
4. **DoctorYa** (https://doctorya.com.ar/) — la vara de WhatsApp conversacional + precio
   publicado + ARCA; demo del bot de reserva y del esquema de planes.
5. **ZynkMed** (https://zynkmed.com.ar/) — la vara de producto integrado con sitio propio
   + lista de espera + inbox WA; demo del flujo de huecos y del portal paciente.

### D.2. Tres productos de referencia para experiencia de usuario

1. **Fresha** (https://www.fresha.com/business) — reserva en 3 clics, marketplace,
   anti-no-show con pagos; copiar velocidad y simplicidad del lado paciente.
2. **Doctoralia** (https://www.doctoraliar.com/) — búsqueda, reputación verificada y
   reserva multicanal; copiar descubrimiento y confianza.
3. **NexHealth** (https://www.nexhealth.com/doctors) — formularios, recordatorios y
   lista de espera que se llena sola; copiar automatización invisible (el turno se
   gestiona solo).

### D.3. MVP sugerido

**Imprescindibles (v1)** — sin esto no se compite:
- Agenda por profesional (diaria/semanal), multi-profesional desde el día 1, con
  duraciones variables y prevención de solapamientos (ya en Discovery: mantener).
- Reserva online 24/7 con link compartible + reserva sin login (DNI/teléfono) y datos
  obligatorios (ya en Discovery: mantener).
- **Recordatorios por WhatsApp** con confirmar/cancelar que actualiza la agenda
  (elevar vs. Discovery v1 "solo mail": el mercado lo exige; mail como fallback).
- Cancelación con antelación configurable (3 h iniciales) + reprogramación por el paciente.
- CRUD recepción completo + bloqueos y sobreturnos.
- Ficha básica del paciente con archivos (puente a la HC post-v1).
- Roles y permisos (recepción / odontólogo / admin) + auditoría mínima.
- Reportes básicos (ocupación, ausentismo, turnos por profesional).
- Mobile-first (ya en Discovery: mantener) + prueba gratuita y precios ARS publicados.

**Diferenciadores v1/v1.1** (ganan contra incumbentes):
- Verificación de obra social en la reserva (formato + copago visible; padrón donde sea
  viable — responde la pregunta abierta del Discovery con evidencia ClinIA/DoctorYa).
- Lista de espera con oferta automática de huecos.
- Seña por Mercado Pago + política de no-show (piso probado por DarTurnos/Fresha).
- Exportación de datos garantizada + declaración Ley 25.326 (confianza).
- Sitio/link de reserva con marca del consultorio.

**Para etapas posteriores** (no v1):
- Odontograma/periodontograma full + planes de tratamiento y presupuestos (diferencial
  clínico grande, pero costoso; post-v1 como ya prevé el Discovery con HC).
- Facturación ARCA y liquidaciones de obras sociales (complejidad regulatoria; primero
  el circuito de turnos).
- Campañas de recupero de inactivos y controles periódicos automatizados.
- Chatbot de reserva conversacional 24/7 (segunda ola, tras dominar recordatorios WA).
- Firma digital, dictado por voz/IA clínica, multi-sucursal, API pública y Google
  Calendar (demanda evidenciada pero no crítica para el segmento inicial).

---

## Verificación de fuentes

El 2026-10-12 se abrieron y comprobaron personalmente 6 fuentes de 5 tipos distintos
(sitio oficial, página de precios, centro de ayuda, documentación de precios, página de
producto con precios AR). Para cada una se anotó qué afirmaba el informe, qué se encontró y
qué se corrigió. Ningún hallazgo invalida las conclusiones del informe; tres correcciones
elevan evidencia (Mercado Pago y odontograma) y una actualiza precios.

| # | Fuente (URL + fecha verificación) | Tipo | Qué afirmaba el informe | Qué se encontró | Veredicto / corrección aplicada |
|---|---|---|---|---|---|
| F-1 | https://www.softwaredentalink.com/ — verificada 2026-10-12 | Sitio oficial | Líder LatAm dental; agenda con estados/sobreagenda; odontograma + IA; sin precios ("Solicita tu cotización"); cifras +15.000 clientes / +12M pacientes / +45M citas / +20 países como afirmación comercial | Home confirma: SaaS 100% nube, agendamiento online, confirmaciones, odontograma y periodontograma, firma electrónica, IA (Clinical Copilot, notas por voz, RX), "+15.000 clínicas", "+20 países", "+100K profesionales", "+16 años", ISO 27001/HIPAA/GDPR; planes Esencial/Pro/Titanium "a cotizar" (sin montos) | **Confirmado.** Ajuste menor: las cifras de pacientes/citas no visibles en home se mantienen como afirmación comercial (marca agregada en fila 1) |
| F-2 | https://doctorya.com.ar/ — verificada 2026-10-12 | Sitio oficial + página de precios | Bot WA con CONFIRMAR/CANCELAR; ARCA; planes $9.000/$25.000/$90.000; Mercado Pago: No evidenciado; odontograma con profundidad No evidenciada | Confirmados agenda, bot WA, ARCA, ficha con odontograma y los 3 montos. **Nuevo:** el home muestra "Pagos con Mercado Pago" (mención no relevada en v1). El tercer plan figura rotulado "Argenti" en el sitio | **Ajustar aplicado:** Mercado Pago pasa a "mención comprobada en home; detalle técnico No evidenciado" (fila 4); nota sobre el rotulado del tercer plan |
| F-3 | https://www.fresha.com/pricing — verificada 2026-10-12 | Página de precios | Independent USD 19,95/mes; Team USD 14,95/miembro/mes; comisión 20% primer turno marketplace; procesamiento ~2,29–2,79% + USD 0,20 | Página actual geolocalizada AR: Independent **ARS 8.000/mes**, Team **ARS 5.300/miembro/mes**, prueba 7 días, WhatsApp ARS 180–375, comparador con marketplace "Free"; la comisión del 20% y el procesamiento citado no aparecen | **Ajustar aplicado:** precios actualizados a ARS vigentes (fila 18); valores USD/comisión anterior marcados como No evidenciado en la página actual |
| F-4 | https://www.opendental.com/site/fees.html — verificada 2026-10-12 | Documentación de precios (vendor open-source) | USD 199/mes/consultorio hasta 3 prestadores; eServices/ODTouch/ODMobile adicionales; facultades gratis | Página de fees confirma literal: "Initial Rate $199/month/location… up to 3 providers", eServices bundle $165/mes, Web Sched $75, escuelas gratis | **Confirmado sin cambios** (fila 14) |
| F-5 | https://zynkmed.com.ar/ — verificada 2026-10-12 | Sitio oficial + página de producto con precios AR | Agenda, sitio propio, lista de espera, inbox WA; precios $150.000/$200.000 + HC $15.000; Mercado Pago como "parcial (marca no verificada)" | Confirmado todo. **Nuevo:** "Cobro online… con Mercado Pago. Cada profesional vincula su propia cuenta de Mercado Pago"; precios idénticos; API oficial de WhatsApp declarada; sin odontograma (HC médica general) | **Ajustar aplicado:** Mercado Pago pasa a comprobado (fila 5); precios confirmados sin cambios |
| F-6 | https://doctorya.com.ar/ayuda — verificada 2026-10-12 | Centro de ayuda | (Cubre transversalmente agenda, recordatorios, ARCA, coberturas) | El centro de ayuda existe y es público, con guías de agenda/horarios, carga de turnos, **"Ficha Clínica, archivos adjuntos y odontograma"**, recordatorios automáticos, coberturas/copagos y facturación ARCA | **Confirmado + Ajustar aplicado:** odontograma de DoctorYa elevado a "comprobado a nivel de centro de ayuda; profundidad funcional No evidenciada en demo pública" (fila 4) |

**Correcciones con Ajustar (resumen):** (1) DoctorYa–Mercado Pago: de "No evidenciado" a mención
comprobada; (2) DoctorYa–odontograma: de "mencionado/profundidad no evidenciada" a comprobado a
nivel de centro de ayuda; (3) ZynkMed–Mercado Pago: de "parcial" a comprobado;
(4) Fresha–precios: actualizados a ARS vigentes, valores USD/comisión anterior a No evidenciado;
(5) Limpieza metodológica: "MediFlow" (C.1), "Dentipilot" (C.2), "tab32" (C.2), "Medec" (C.4) y la
fila "CareStack" de la matriz (B) quedaron marcados como **No evidenciado / sin fuente en Tabla A**
por no tener URL ni entrada en la tabla (no se eliminaron, se señalizaron: es lo que la consigna
pide hacer con lo no respaldado).

---

## Referencias completas

Fuentes originales (consulta 2026-10-10/11) y verificación (2026-10-12). Todas las URLs se
abrieron como páginas públicas; no se crearon cuentas ni se contactó a proveedores (ver
Consideraciones de la consigna). Datos de pacientes: no aplica — no se usaron datos reales
(regla dura del proyecto: solo datos ficticios).

**Sitios oficiales (Tabla A, filas 1–18):**
1. Dentalink — https://www.softwaredentalink.com/ (consulta 2026-10-10/11; verificación 2026-10-12)
2. Odentix — https://odentix.framer.website/ (2026-10-10/11)
3. ClinIA — https://www.clinia.com.ar/software-para-clinicas (2026-10-10/11)
4. DoctorYa — https://doctorya.com.ar/ (2026-10-10/11; verificación home + ayuda 2026-10-12)
5. ZynkMed — https://zynkmed.com.ar/ (2026-10-10/11; verificación 2026-10-12)
6. MediTurn — https://mediturn.com.ar/ (2026-10-10/11)
7. Medilink — https://www.softwaremedilink.com/ (2026-10-10/11)
8. AgendaPro — https://agendapro.com/ (2026-10-10/11)
9. dt.dental — https://dtdental.co/ (2026-10-10/11)
10. Docturno — https://www.docturno.com/ (2026-10-10/11)
11. Doctoralia AR — https://www.doctoraliar.com/ · PRO AR — https://pro.doctoralia.com/ar/agenda-doctoralia-para-especialistas (2026-10-10/11)
12. Meducar — http://meducar.com/ (2026-10-10/11)
13. DarTurnos — https://darturnos.com/ (2026-10-10/11)
14. Open Dental — https://www.opendental.com/ · fees — https://www.opendental.com/site/fees.html (2026-10-10/11; verificación fees 2026-10-12)
15. Dentrix — https://www.dentrix.com/ (2026-10-10/11)
16. Curve Dental — https://www.curvedental.com/ (2026-10-10/11)
17. NexHealth — https://www.nexhealth.com/doctors · https://try.nexhealth.com/for-dental (2026-10-10/11)
18. Fresha — https://www.fresha.com/business · pricing — https://www.fresha.com/pricing (2026-10-10/11; verificación pricing 2026-10-12)

**Páginas de precios/funcionalidad citadas en celdas:** Doctoralia precios CL —
https://pro.doctoralia.cl/precios; comparador Capterra Curve vs CareStack —
https://www.capterra.com/compare/98688-176206/Curve-Dental-Hero-vs-CareStack; reseña Pabau sobre
Fresha (2026-08-25, citada en fuente histórica); ficha Tracxn Docturno; DEXIS (referencia de
imagenología, excluido por no ser PMS) — https://dexis.com/es-es.
**Actor del ecosistema (no competidor):** Consulmed — https://www.consulmed.com.ar/.

**Documento de trabajo del equipo:** `desarrollo-active-stack.pdf` (Etapa 2, pp. 3–4; Entregables,
pp. 7–8). **Fuentes históricas del repo:** `discovery/market-research-odontologia-AR.md`,
`discovery/discovery.md` (checklist 11 puntos, copiado fiel en
`docs/discovery/checklist-11-puntos.md`).

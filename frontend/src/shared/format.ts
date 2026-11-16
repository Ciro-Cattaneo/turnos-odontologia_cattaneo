/** Formateo visible siempre en la zona del consultorio (R15, D-5/D-6). */

export const ZONA_CONSULTORIO = "America/Argentina/Buenos_Aires";

const formatoHora = new Intl.DateTimeFormat("es-AR", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: ZONA_CONSULTORIO,
});

const formatoFecha = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: ZONA_CONSULTORIO,
});

const formatoPartesFecha = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: ZONA_CONSULTORIO,
});

export function formatearHora(iso: string): string {
  return formatoHora.format(new Date(iso));
}

export function formatearFecha(iso: string): string {
  return formatoFecha.format(new Date(iso));
}

export function formatearDuracion(minutos: number): string {
  return `${minutos} min`;
}

export function formatearFechaHora(iso: string): string {
  return `${formatearFecha(iso)} ${formatearHora(iso)}`;
}

/** Etiqueta de un día calendario `YYYY-MM-DD` sin reinterpretarlo como instante. */
export function formatearFechaCalendario(fecha: string): string {
  const [anio, mes, dia] = fecha.split("-");
  if (anio === undefined || mes === undefined || dia === undefined) {
    return fecha;
  }
  return `${dia}/${mes}/${anio}`;
}

function parte(partes: Intl.DateTimeFormatPart[], tipo: string): string {
  return partes.find((p) => p.type === tipo)?.value ?? "";
}

/** Día calendario `YYYY-MM-DD` del consultorio para un instante dado. */
export function fechaEnConsultorio(instante: Date): string {
  const partes = formatoPartesFecha.formatToParts(instante);
  return `${parte(partes, "year")}-${parte(partes, "month")}-${parte(partes, "day")}`;
}

/** Día calendario del consultorio hoy (independiente de la TZ del navegador). */
export function hoyEnConsultorio(instante: Date = new Date()): string {
  return fechaEnConsultorio(instante);
}

/** Suma días a una fecha calendario `YYYY-MM-DD` sin depender de la TZ local. */
export function addDias(fecha: string, dias: number): string {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  const base = new Date(Date.UTC(anio, mes - 1, dia));
  base.setUTCDate(base.getUTCDate() + dias);
  return base.toISOString().slice(0, 10);
}

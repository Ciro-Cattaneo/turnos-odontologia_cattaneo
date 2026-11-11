/** Formateo visible siempre en la zona del consultorio (R15, D-5). */

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

export function formatearHora(iso: string): string {
  return formatoHora.format(new Date(iso));
}

export function formatearFecha(iso: string): string {
  return formatoFecha.format(new Date(iso));
}

export function formatearDuracion(minutos: number): string {
  return `${minutos} min`;
}

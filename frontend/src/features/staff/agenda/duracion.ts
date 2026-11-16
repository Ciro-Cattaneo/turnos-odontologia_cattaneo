/**
 * Duración del alta de recepción: opciones múltiplos de la granularidad del
 * profesional y validación local defensiva (§6.2, RN-TU-03).
 */

const MAX_BLOQUES_DURACION = 4;

export function opcionesDuracion(granularidad: number): number[] {
  const base =
    Number.isFinite(granularidad) && granularidad > 0
      ? Math.round(granularidad)
      : 30;
  const opciones: number[] = [];
  for (let bloque = 1; bloque <= MAX_BLOQUES_DURACION; bloque += 1) {
    opciones.push(base * bloque);
  }
  return opciones;
}

export function esDuracionValida(
  duracion: number,
  granularidad: number,
): boolean {
  const base =
    Number.isFinite(granularidad) && granularidad > 0
      ? Math.round(granularidad)
      : 30;
  return Number.isFinite(duracion) && duracion > 0 && duracion % base === 0;
}

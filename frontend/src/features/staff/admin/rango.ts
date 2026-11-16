/** Rango del reporte: default de 30 días y validación local ≤366 (RE R1/R3). */

import { addDias, hoyEnConsultorio } from "../../../shared/format";

export const MAX_DIAS_REPORTE = 366;

export interface RangoReporte {
  desde: string;
  hasta: string;
}

export interface ErroresRango {
  desde?: string;
  hasta?: string;
}

/** Últimos 30 días inclusivos en el calendario del consultorio. */
export function rangoPorDefecto(hoy: string = hoyEnConsultorio()): RangoReporte {
  return { desde: addDias(hoy, -29), hasta: hoy };
}

function aUTC(fecha: string): number {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  return Date.UTC(anio, mes - 1, dia);
}

/** Días calendario inclusivos entre dos fechas `YYYY-MM-DD`. */
export function diasInclusivos(desde: string, hasta: string): number {
  return Math.round((aUTC(hasta) - aUTC(desde)) / 86_400_000) + 1;
}

/**
 * Validación local espejo del backend: rango invertido y tope de 366 días
 * inclusivos se informan siempre en `hasta` (campo del contrato).
 */
export function validarRango(desde: string, hasta: string): ErroresRango {
  const errores: ErroresRango = {};
  if (desde === "") {
    errores.desde = "Elegí una fecha desde.";
  }
  if (hasta === "") {
    errores.hasta = "Elegí una fecha hasta.";
  }
  if (errores.desde !== undefined || errores.hasta !== undefined) {
    return errores;
  }
  const dias = diasInclusivos(desde, hasta);
  if (dias <= 0) {
    errores.hasta =
      "La fecha hasta no puede ser anterior a la fecha desde.";
  } else if (dias > MAX_DIAS_REPORTE) {
    errores.hasta = `El rango máximo es de ${MAX_DIAS_REPORTE} días inclusive.`;
  }
  return errores;
}

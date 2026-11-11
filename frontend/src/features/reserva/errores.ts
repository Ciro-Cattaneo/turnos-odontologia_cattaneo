/** Describe errores del borde HTTP en mensajes accionables (D-6). */

import { ApiError, ApiHttpError } from "../../shared/api/client";
import type { BusquedaError } from "./types";

export function mensajeEspera(retryAfter?: number): string {
  if (retryAfter === undefined) {
    return "Demasiados intentos. Esperá un momento antes de reintentar.";
  }
  const unidad = retryAfter === 1 ? "segundo" : "segundos";
  return `Demasiados intentos. Esperá ${retryAfter} ${unidad} antes de reintentar.`;
}

export function describirError(err: unknown): BusquedaError {
  if (err instanceof ApiHttpError) {
    if (err.status === 429) {
      const error: BusquedaError = {
        kind: "rate_limit",
        message: mensajeEspera(err.retryAfter),
      };
      if (err.retryAfter !== undefined) {
        error.retryAfter = err.retryAfter;
      }
      return error;
    }
    if (err.status === 404) {
      return {
        kind: "no_disponible",
        message:
          "El profesional no está disponible. Recargá la lista o elegí otro profesional.",
      };
    }
    return {
      kind: "unexpected",
      message: "No pudimos completar la operación. Intentá de nuevo.",
    };
  }
  if (err instanceof ApiError && err.code === "NETWORK_ERROR") {
    return {
      kind: "network",
      message: "No pudimos conectarnos. Revisá tu conexión e intentá de nuevo.",
    };
  }
  return {
    kind: "unexpected",
    message: "La respuesta del servidor no es válida. Intentá de nuevo.",
  };
}

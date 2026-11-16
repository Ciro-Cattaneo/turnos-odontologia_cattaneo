/** Traducción uniforme de errores staff a mensajes accionables (D-13). */

import {
  ApiError,
  ApiHttpError,
  isAlternativosDetail,
  type ApiErrorDetail,
  type Slot,
} from "./client";

export type StaffErrorKind =
  | "field"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limit"
  | "network"
  | "unexpected";

export interface StaffErrorInfo {
  kind: StaffErrorKind;
  message: string;
  fieldErrors: Record<string, string>;
  alternativos: Slot[];
  codigo: string | null;
  retryAfter?: number;
}

const MENSAJES_422: Record<string, string> = {
  ultimo_admin:
    "Debe quedar al menos un admin activo. Asigná el rol a otro usuario antes de cambiar o dar de baja este.",
  motivo_requerido:
    "Se requiere un motivo para cancelar con menos de 3 horas de anticipación.",
  turno_no_editable: "El turno ya no se puede editar en su estado actual.",
  turno_ya_cancelado: "El turno ya está cancelado.",
  turno_no_cancelable: "El turno no se puede cancelar en su estado actual.",
  transicion_invalida:
    "La transición de estado no es válida para el estado actual del turno.",
};

function vacio(kind: StaffErrorKind, message: string): StaffErrorInfo {
  return {
    kind,
    message,
    fieldErrors: {},
    alternativos: [],
    codigo: null,
  };
}

function mensajeEspera(retryAfter?: number): string {
  if (retryAfter === undefined) {
    return "Demasiados intentos. Esperá un momento antes de reintentar.";
  }
  const unidad = retryAfter === 1 ? "segundo" : "segundos";
  return `Demasiados intentos. Esperá ${retryAfter} ${unidad} antes de reintentar.`;
}

function codigoDe(detail: ApiErrorDetail): string | null {
  if (detail !== null && !Array.isArray(detail) && typeof detail === "object") {
    return detail.codigo;
  }
  return null;
}

function normalizarCampo(campo: string): string {
  const sinCuerpo = campo.startsWith("body.")
    ? campo.slice("body.".length)
    : campo;
  const prefijo = "paciente.";
  return sinCuerpo.startsWith(prefijo)
    ? sinCuerpo.slice(prefijo.length)
    : sinCuerpo;
}

function camposDe(detail: ApiErrorDetail): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  if (!Array.isArray(detail)) {
    return fieldErrors;
  }
  for (const item of detail) {
    fieldErrors[normalizarCampo(item.campo)] = item.error;
  }
  return fieldErrors;
}

function desdeHttp(error: ApiHttpError, contexto: string): StaffErrorInfo {
  if (error.status === 400) {
    const fieldErrors = camposDe(error.detail);
    const info = vacio(
      "field",
      Object.keys(fieldErrors).length > 0
        ? "Revisá los datos marcados."
        : "La solicitud no es válida.",
    );
    return { ...info, fieldErrors };
  }
  if (error.status === 401) {
    return vacio(
      "unauthorized",
      "Tu sesión expiró. Volvé a iniciar sesión.",
    );
  }
  if (error.status === 403) {
    return vacio("forbidden", "No tenés permiso para esta acción.");
  }
  if (error.status === 404) {
    return vacio("not_found", "No encontrado.");
  }
  if (error.status === 409) {
    const codigo = codigoDe(error.detail);
    if (codigo === "email_duplicado") {
      return {
        ...vacio(
          "conflict",
          "Ese email ya está tomado, incluso por un usuario inactivo. Reactivá la fila existente en lugar de crear una nueva.",
        ),
        codigo,
      };
    }
    if (codigo === "dni_duplicado") {
      return {
        ...vacio(
          "conflict",
          "Ese DNI ya está registrado en otro paciente. No se fusionaron los datos.",
        ),
        codigo,
      };
    }
    const alternativos = isAlternativosDetail(error.detail)
      ? error.detail.alternativos
      : [];
    return {
      ...vacio("conflict", "El horario elegido ya no está disponible."),
      alternativos,
      codigo,
    };
  }
  if (error.status === 422) {
    if (Array.isArray(error.detail)) {
      const fieldErrors = camposDe(error.detail);
      return { ...vacio("field", "Revisá los datos marcados."), fieldErrors };
    }
    const codigo = codigoDe(error.detail);
    return {
      ...vacio(
        "validation",
        (codigo !== null ? MENSAJES_422[codigo] : undefined) ??
          "El turno no admite esta operación en su estado actual.",
      ),
      codigo,
    };
  }
  if (error.status === 429) {
    return {
      ...vacio("rate_limit", mensajeEspera(error.retryAfter)),
      ...(error.retryAfter !== undefined ? { retryAfter: error.retryAfter } : {}),
    };
  }
  return vacio(
    "unexpected",
    `No pudimos completar ${contexto}. Intentá de nuevo.`,
  );
}

export function mensajeDeError(
  error: unknown,
  contexto = "la operación",
): StaffErrorInfo {
  if (error instanceof ApiHttpError) {
    return desdeHttp(error, contexto);
  }
  if (error instanceof ApiError && error.code === "NETWORK_ERROR") {
    return vacio(
      "network",
      "No pudimos conectarnos. Revisá tu conexión e intentá de nuevo.",
    );
  }
  if (error instanceof ApiError) {
    return vacio(
      "unexpected",
      "La respuesta del servidor no es válida. Intentá de nuevo.",
    );
  }
  return vacio(
    "unexpected",
    `No pudimos completar ${contexto}. Intentá de nuevo.`,
  );
}

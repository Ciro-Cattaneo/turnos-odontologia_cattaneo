/** Validación local del formulario y mapeo del 400 por campo (D-4, D-6). */

import type { ApiErrorDetail } from "../../shared/api/client";
import {
  FORM_FIELDS,
  type FormErrors,
  type FormField,
  type FormValues,
} from "./types";

const EMAIL_PATTERN = /.+@.+\..+/;

export const MENSAJE_ERROR_SLOT =
  "Ese horario ya no está disponible. Volvé a consultar la disponibilidad.";

export function isFormField(value: string): value is FormField {
  return (FORM_FIELDS as readonly string[]).includes(value);
}

export function validarFormulario(values: FormValues): FormErrors {
  const errors: FormErrors = {};
  if (values.nombre.trim() === "") {
    errors.nombre = "Ingresá tu nombre y apellido.";
  }
  if (values.dni.trim() === "") {
    errors.dni = "Ingresá tu DNI.";
  }
  if (values.telefono.trim() === "") {
    errors.telefono = "Ingresá tu teléfono.";
  }
  if (values.obra_social.trim() === "") {
    errors.obra_social = "Ingresá tu obra social.";
  }
  const email = values.email.trim();
  if (email === "") {
    errors.email = "Ingresá tu email.";
  } else if (!EMAIL_PATTERN.test(email)) {
    errors.email = "Ingresá un email válido.";
  }
  return errors;
}

export interface DetalleFormulario {
  fieldErrors: FormErrors;
  slotError: string | null;
  otroError: string | null;
}

export function mapearDetalle400(detail: ApiErrorDetail): DetalleFormulario {
  const fieldErrors: FormErrors = {};
  let slotError: string | null = null;
  let otroError: string | null = null;
  if (!Array.isArray(detail)) {
    return { fieldErrors, slotError, otroError };
  }
  for (const item of detail) {
    if (item.campo.startsWith("paciente.")) {
      const campo = item.campo.slice("paciente.".length);
      if (isFormField(campo)) {
        fieldErrors[campo] = item.error;
      }
    } else if (item.campo === "inicio" || item.campo === "duracion_min") {
      slotError = MENSAJE_ERROR_SLOT;
    } else {
      otroError = item.error;
    }
  }
  return { fieldErrors, slotError, otroError };
}

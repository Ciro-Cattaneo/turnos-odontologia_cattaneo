/** Tipos locales del flujo público de reserva (sin estado global, D-9). */

import type { Slot } from "../../shared/api/client";

export interface FormValues {
  nombre: string;
  dni: string;
  telefono: string;
  obra_social: string;
  email: string;
}

export type FormField = keyof FormValues;

export type FormErrors = Partial<Record<FormField, string>>;

export const FORM_FIELDS: readonly FormField[] = [
  "nombre",
  "dni",
  "telefono",
  "obra_social",
  "email",
];

export const FORM_VALUES_VACIOS: FormValues = {
  nombre: "",
  dni: "",
  telefono: "",
  obra_social: "",
  email: "",
};

export interface BusquedaError {
  kind: "network" | "unexpected" | "no_disponible" | "rate_limit";
  message: string;
  retryAfter?: number;
}

export type DisponibilidadStatus =
  | "idle"
  | "loading"
  | "success"
  | "empty"
  | "error";

export interface DisponibilidadState {
  status: DisponibilidadStatus;
  slots: Slot[];
  error: BusquedaError | null;
}

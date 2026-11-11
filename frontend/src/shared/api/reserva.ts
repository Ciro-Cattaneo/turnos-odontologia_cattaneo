/** Endpoints públicos de reserva y cancelación, con guards estrictos del contrato. */

import {
  API_BASE,
  isRecord,
  isSlot,
  requestWithDetail,
  type Slot,
} from "./client";

export type { Slot };

export interface Profesional {
  id: string;
  nombre: string;
  especialidad: string | null;
  matricula: string | null;
  duracion_default_min: number;
  ultima_actualizacion: string | null;
}

export interface ProfesionalesResponse {
  items: Profesional[];
  next_cursor: string | null;
}

export interface DisponibilidadResponse {
  profesional_id: string;
  slots: Slot[];
  ultima_actualizacion: string | null;
}

export interface PacienteInput {
  nombre: string;
  dni: string;
  telefono: string;
  obra_social: string;
  email: string;
}

export interface CrearTurnoBody {
  profesional_id: string;
  inicio: string;
  duracion_min?: number;
  paciente: PacienteInput;
}

export interface TurnoOut {
  id: string;
  estado: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  profesional: { id: string; nombre: string };
  paciente: { nombre: string; dni: string; email: string };
  token_cancelacion: string;
  cancel_url: string;
  notificaciones_encoladas: boolean;
}

export interface CancelacionOut {
  id: string;
  estado: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  notificaciones_encoladas: boolean;
  mensaje: string;
}

export interface RangoDia {
  desde: string;
  hasta: string;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export function isProfesional(value: unknown): value is Profesional {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string" &&
    isNullableString(value["especialidad"]) &&
    isNullableString(value["matricula"]) &&
    typeof value["duracion_default_min"] === "number" &&
    Number.isFinite(value["duracion_default_min"]) &&
    isNullableString(value["ultima_actualizacion"])
  );
}

export function isProfesionalesResponse(
  value: unknown,
): value is ProfesionalesResponse {
  if (!isRecord(value) || !Array.isArray(value["items"])) {
    return false;
  }
  if (
    value["next_cursor"] !== null &&
    typeof value["next_cursor"] !== "string"
  ) {
    return false;
  }
  return value["items"].every(isProfesional);
}

export function isDisponibilidadResponse(
  value: unknown,
): value is DisponibilidadResponse {
  return (
    isRecord(value) &&
    typeof value["profesional_id"] === "string" &&
    Array.isArray(value["slots"]) &&
    value["slots"].every(isSlot) &&
    isNullableString(value["ultima_actualizacion"])
  );
}

function isProfesionalResumen(value: unknown): value is { id: string; nombre: string } {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string"
  );
}

function isPacienteResumen(
  value: unknown,
): value is { nombre: string; dni: string; email: string } {
  return (
    isRecord(value) &&
    typeof value["nombre"] === "string" &&
    typeof value["dni"] === "string" &&
    typeof value["email"] === "string"
  );
}

export function isTurnoOut(value: unknown): value is TurnoOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    typeof value["duracion_min"] === "number" &&
    Number.isFinite(value["duracion_min"]) &&
    isProfesionalResumen(value["profesional"]) &&
    isPacienteResumen(value["paciente"]) &&
    typeof value["token_cancelacion"] === "string" &&
    typeof value["cancel_url"] === "string" &&
    typeof value["notificaciones_encoladas"] === "boolean"
  );
}

export function isCancelacionOut(value: unknown): value is CancelacionOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    typeof value["duracion_min"] === "number" &&
    Number.isFinite(value["duracion_min"]) &&
    typeof value["notificaciones_encoladas"] === "boolean" &&
    typeof value["mensaje"] === "string"
  );
}

/** Rango del día calendario del consultorio (UTC−3, sin horario de verano). */
export function construirRangoDia(fecha: string): RangoDia {
  return {
    desde: `${fecha}T00:00:00-03:00`,
    hasta: `${fecha}T23:59:59-03:00`,
  };
}

export async function getProfesionales(): Promise<Profesional[]> {
  const items: Profesional[] = [];
  let cursor: string | null = null;
  do {
    const query: string =
      cursor === null ? "" : `?cursor=${encodeURIComponent(cursor)}`;
    const page: ProfesionalesResponse =
      await requestWithDetail<ProfesionalesResponse>(
        `${API_BASE}/api/profesionales${query}`,
        isProfesionalesResponse,
      );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor !== null);
  return items;
}

export function getDisponibilidad(
  profesionalId: string,
  desde: string,
  hasta: string,
): Promise<DisponibilidadResponse> {
  const params = new URLSearchParams({
    profesional_id: profesionalId,
    desde,
    hasta,
  });
  return requestWithDetail<DisponibilidadResponse>(
    `${API_BASE}/api/disponibilidad?${params.toString()}`,
    isDisponibilidadResponse,
  );
}

export function getDisponibilidadDia(
  profesionalId: string,
  fecha: string,
): Promise<DisponibilidadResponse> {
  const rango = construirRangoDia(fecha);
  return getDisponibilidad(profesionalId, rango.desde, rango.hasta);
}

export function crearTurno(body: CrearTurnoBody): Promise<TurnoOut> {
  return requestWithDetail<TurnoOut>(`${API_BASE}/api/turnos`, isTurnoOut, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function cancelarTurno(
  id: string,
  token: string,
): Promise<CancelacionOut> {
  const query = new URLSearchParams({ token });
  return requestWithDetail<CancelacionOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}?${query.toString()}`,
    isCancelacionOut,
    { method: "DELETE" },
  );
}

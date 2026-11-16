/**
 * Endpoints staff con sesión por cookie httpOnly (`credentials: "include"`).
 * Guards estrictos por contrato (sin `any`, sin barrels) y reutilización de
 * `requestWithDetail`/`ApiHttpError` de `client.ts` (D-3/D-4/D-16).
 */

import {
  API_BASE,
  isRecord,
  requestWithDetail,
  type Slot,
} from "./client";
import {
  isProfesional,
  type PacienteInput,
  type Profesional,
} from "./reserva";

export const ROLES_STAFF = ["recepcion", "odontologo", "admin"] as const;

export type StaffRol = (typeof ROLES_STAFF)[number];

export type VistaAgenda = "dia" | "semana";

export interface LoginIn {
  email: string;
  password: string;
}

export interface LoginOut {
  email: string;
  rol: StaffRol;
}

export interface LogoutOut {
  ok: boolean;
}

export interface MeOut {
  email: string;
  rol: StaffRol;
  profesional_id: string | null;
}

export interface PacienteMinimo {
  id: string;
  nombre: string;
}

export interface FranjaLibre {
  tipo: "libre";
  inicio: string;
  fin: string;
  duracion_min: number;
}

export interface FranjaOcupado {
  tipo: "ocupado";
  turno_id: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  estado: string;
  paciente: PacienteMinimo;
}

export interface FranjaBloqueado {
  tipo: "bloqueado";
  inicio: string;
  fin: string;
  motivo: string;
}

export interface FranjaCerrado {
  tipo: "cerrado";
  turno_id: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  estado: string;
  paciente: PacienteMinimo;
}

export type FranjaStaff =
  | FranjaLibre
  | FranjaOcupado
  | FranjaBloqueado
  | FranjaCerrado;

export interface AgendaDia {
  fecha: string;
  franjas: FranjaStaff[];
}

export interface AgendaResponse {
  profesional_id: string;
  vista: VistaAgenda;
  dias: AgendaDia[];
  next_cursor: string;
  ultima_actualizacion: string | null;
}

export interface CrearTurnoStaffBody {
  profesional_id: string;
  inicio: string;
  duracion_min?: number;
  origen: "recepcion";
  paciente: PacienteInput;
}

export interface TurnoStaffOut {
  id: string;
  estado: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  notificaciones_encoladas: boolean;
}

export interface ReprogramacionBody {
  inicio?: string;
  duracion_min?: number;
}

export interface ReprogramacionOut {
  id: string;
  estado: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  notificaciones_encoladas: boolean;
}

export interface CorreccionPacienteBody {
  dni?: string;
  telefono?: string;
  obra_social?: string;
}

export interface PacienteCorregidoOut {
  id: string;
  nombre: string | null;
  dni: string | null;
  telefono: string | null;
  obra_social: string | null;
  email: string | null;
  activo: boolean;
}

export interface CorreccionPacienteOut {
  id: string;
  paciente: PacienteCorregidoOut;
  notificaciones_encoladas: boolean;
}

export type EstadoTurnoStaff = "confirmado" | "atendido" | "ausente";

export interface EstadoOut {
  id: string;
  estado: string;
  estado_previo: string;
  notificaciones_encoladas: boolean;
}

export interface ProfesionalFicha {
  id: string;
  nombre: string;
  especialidad: string | null;
}

export interface PacienteFicha {
  id: string;
  nombre: string | null;
  dni: string | null;
  telefono: string | null;
  obra_social: string | null;
  email: string | null;
  activo: boolean;
}

export interface AuditoriaItem {
  id: string;
  accion: string;
  actor: Record<string, unknown>;
  created_at: string;
  detalle: Record<string, unknown>;
}

export interface AuditoriaPage {
  items: AuditoriaItem[];
  next_cursor: string | null;
}

export interface TurnoFichaOut {
  id: string;
  estado: string;
  origen: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  profesional: ProfesionalFicha;
  paciente: PacienteFicha;
  auditoria: AuditoriaPage;
}

export interface CancelacionStaffOut {
  id: string;
  estado: string;
  inicio: string;
  fin: string;
  duracion_min: number;
  notificaciones_encoladas: boolean;
  mensaje: string;
}

export interface FallidaItem {
  id: string;
  turno_id: string;
  tipo: string;
  intentos: number;
  error: string | null;
  enviar_en: string | null;
  paciente_nombre: string | null;
  paciente_email: string | null;
  inicio: string;
  fin: string;
}

export interface FallidasPage {
  items: FallidaItem[];
  next_cursor: string | null;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function isStaffRol(value: unknown): value is StaffRol {
  return (
    typeof value === "string" &&
    (ROLES_STAFF as readonly string[]).includes(value)
  );
}

export function isLoginOut(value: unknown): value is LoginOut {
  return (
    isRecord(value) &&
    typeof value["email"] === "string" &&
    isStaffRol(value["rol"])
  );
}

export function isLogoutOut(value: unknown): value is LogoutOut {
  return isRecord(value) && value["ok"] === true;
}

export function isMeOut(value: unknown): value is MeOut {
  return (
    isRecord(value) &&
    typeof value["email"] === "string" &&
    isStaffRol(value["rol"]) &&
    isNullableString(value["profesional_id"])
  );
}

function isPacienteMinimo(value: unknown): value is PacienteMinimo {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string"
  );
}

function isRango(value: Record<string, unknown>): boolean {
  return typeof value["inicio"] === "string" && typeof value["fin"] === "string";
}

export function isFranjaStaff(value: unknown): value is FranjaStaff {
  if (!isRecord(value) || !isRango(value)) {
    return false;
  }
  if (value["tipo"] === "libre") {
    return isFiniteNumber(value["duracion_min"]);
  }
  if (value["tipo"] === "bloqueado") {
    return typeof value["motivo"] === "string";
  }
  if (value["tipo"] === "ocupado" || value["tipo"] === "cerrado") {
    return (
      typeof value["turno_id"] === "string" &&
      isFiniteNumber(value["duracion_min"]) &&
      typeof value["estado"] === "string" &&
      isPacienteMinimo(value["paciente"])
    );
  }
  return false;
}

function isAgendaDia(value: unknown): value is AgendaDia {
  return (
    isRecord(value) &&
    typeof value["fecha"] === "string" &&
    Array.isArray(value["franjas"]) &&
    value["franjas"].every(isFranjaStaff)
  );
}

export function isAgendaResponse(value: unknown): value is AgendaResponse {
  return (
    isRecord(value) &&
    typeof value["profesional_id"] === "string" &&
    (value["vista"] === "dia" || value["vista"] === "semana") &&
    Array.isArray(value["dias"]) &&
    value["dias"].every(isAgendaDia) &&
    typeof value["next_cursor"] === "string" &&
    isNullableString(value["ultima_actualizacion"])
  );
}

export function isProfesionalesStaffPage(
  value: unknown,
): value is { items: Profesional[]; next_cursor: string | null } {
  if (!isRecord(value) || !Array.isArray(value["items"])) {
    return false;
  }
  if (!isNullableString(value["next_cursor"])) {
    return false;
  }
  return value["items"].every(isProfesional);
}

export function isTurnoStaffOut(value: unknown): value is TurnoStaffOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    isFiniteNumber(value["duracion_min"]) &&
    typeof value["notificaciones_encoladas"] === "boolean"
  );
}

export function isReprogramacionOut(
  value: unknown,
): value is ReprogramacionOut {
  return isTurnoStaffOut(value);
}

export function isEstadoOut(value: unknown): value is EstadoOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["estado_previo"] === "string" &&
    typeof value["notificaciones_encoladas"] === "boolean"
  );
}

function isProfesionalFicha(value: unknown): value is ProfesionalFicha {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string" &&
    isNullableString(value["especialidad"])
  );
}

function isPacienteFicha(value: unknown): value is PacienteFicha {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    isNullableString(value["nombre"]) &&
    isNullableString(value["dni"]) &&
    isNullableString(value["telefono"]) &&
    isNullableString(value["obra_social"]) &&
    isNullableString(value["email"]) &&
    typeof value["activo"] === "boolean"
  );
}

function isAuditoriaItem(value: unknown): value is AuditoriaItem {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["accion"] === "string" &&
    isRecord(value["actor"]) &&
    typeof value["created_at"] === "string" &&
    isRecord(value["detalle"])
  );
}

function isAuditoriaPage(value: unknown): value is AuditoriaPage {
  return (
    isRecord(value) &&
    Array.isArray(value["items"]) &&
    value["items"].every(isAuditoriaItem) &&
    isNullableString(value["next_cursor"])
  );
}

export function isFichaOut(value: unknown): value is TurnoFichaOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["origen"] === "string" &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    isFiniteNumber(value["duracion_min"]) &&
    isProfesionalFicha(value["profesional"]) &&
    isPacienteFicha(value["paciente"]) &&
    isAuditoriaPage(value["auditoria"])
  );
}

function isPacienteCorregidoOut(value: unknown): value is PacienteCorregidoOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    isNullableString(value["nombre"]) &&
    isNullableString(value["dni"]) &&
    isNullableString(value["telefono"]) &&
    isNullableString(value["obra_social"]) &&
    isNullableString(value["email"]) &&
    typeof value["activo"] === "boolean"
  );
}

export function isCorreccionOut(value: unknown): value is CorreccionPacienteOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    isPacienteCorregidoOut(value["paciente"]) &&
    typeof value["notificaciones_encoladas"] === "boolean"
  );
}

export function isCancelacionStaffOut(
  value: unknown,
): value is CancelacionStaffOut {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["estado"] === "string" &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    isFiniteNumber(value["duracion_min"]) &&
    typeof value["notificaciones_encoladas"] === "boolean" &&
    typeof value["mensaje"] === "string"
  );
}

function isFallidaItem(value: unknown): value is FallidaItem {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["turno_id"] === "string" &&
    typeof value["tipo"] === "string" &&
    typeof value["intentos"] === "number" &&
    isNullableString(value["error"]) &&
    isNullableString(value["enviar_en"]) &&
    isNullableString(value["paciente_nombre"]) &&
    isNullableString(value["paciente_email"]) &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string"
  );
}

export function isFallidasPage(value: unknown): value is FallidasPage {
  return (
    isRecord(value) &&
    Array.isArray(value["items"]) &&
    value["items"].every(isFallidaItem) &&
    isNullableString(value["next_cursor"])
  );
}

const CREDENCIALES: RequestInit = { credentials: "include" };

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    ...CREDENCIALES,
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function login(body: LoginIn): Promise<LoginOut> {
  return requestWithDetail<LoginOut>(
    `${API_BASE}/api/auth/login`,
    isLoginOut,
    jsonInit("POST", body),
  );
}

export function logout(): Promise<LogoutOut> {
  return requestWithDetail<LogoutOut>(
    `${API_BASE}/api/auth/logout`,
    isLogoutOut,
    { ...CREDENCIALES, method: "POST" },
  );
}

export function me(): Promise<MeOut> {
  return requestWithDetail<MeOut>(
    `${API_BASE}/api/auth/me`,
    isMeOut,
    CREDENCIALES,
  );
}

export async function getProfesionalesStaff(): Promise<Profesional[]> {
  const items: Profesional[] = [];
  let cursor: string | null = null;
  do {
    const query: string =
      cursor === null ? "" : `?cursor=${encodeURIComponent(cursor)}`;
    const page = await requestWithDetail<
      { items: Profesional[]; next_cursor: string | null }
    >(
      `${API_BASE}/api/profesionales${query}`,
      isProfesionalesStaffPage,
      CREDENCIALES,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor !== null);
  return items;
}

export function getAgenda(
  profesionalId: string,
  vista: VistaAgenda,
  fecha: string,
): Promise<AgendaResponse> {
  const params = new URLSearchParams({ vista, fecha });
  return requestWithDetail<AgendaResponse>(
    `${API_BASE}/api/profesionales/${encodeURIComponent(profesionalId)}/agenda?${params.toString()}`,
    isAgendaResponse,
    CREDENCIALES,
  );
}

export function crearTurnoRecepcion(
  body: CrearTurnoStaffBody,
): Promise<TurnoStaffOut> {
  return requestWithDetail<TurnoStaffOut>(
    `${API_BASE}/api/turnos`,
    isTurnoStaffOut,
    jsonInit("POST", body),
  );
}

export function reprogramar(
  id: string,
  body: ReprogramacionBody,
): Promise<ReprogramacionOut> {
  return requestWithDetail<ReprogramacionOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}`,
    isReprogramacionOut,
    jsonInit("PUT", body),
  );
}

export function cancelar(
  id: string,
  motivo?: string,
): Promise<CancelacionStaffOut> {
  const body: { motivo?: string } = motivo === undefined ? {} : { motivo };
  return requestWithDetail<CancelacionStaffOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}`,
    isCancelacionStaffOut,
    jsonInit("DELETE", body),
  );
}

export function corregirPaciente(
  id: string,
  body: CorreccionPacienteBody,
): Promise<CorreccionPacienteOut> {
  return requestWithDetail<CorreccionPacienteOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}/paciente`,
    isCorreccionOut,
    jsonInit("PUT", body),
  );
}

export function cambiarEstado(
  id: string,
  estado: EstadoTurnoStaff,
): Promise<EstadoOut> {
  return requestWithDetail<EstadoOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}/estado`,
    isEstadoOut,
    jsonInit("PATCH", { estado }),
  );
}

export function getFicha(
  id: string,
  historialCursor?: string,
): Promise<TurnoFichaOut> {
  const query =
    historialCursor === undefined
      ? ""
      : `?${new URLSearchParams({ historial_cursor: historialCursor }).toString()}`;
  return requestWithDetail<TurnoFichaOut>(
    `${API_BASE}/api/turnos/${encodeURIComponent(id)}${query}`,
    isFichaOut,
    CREDENCIALES,
  );
}

export function getFallidas(cursor?: string): Promise<FallidasPage> {
  const params = new URLSearchParams({ limit: "20" });
  if (cursor !== undefined) {
    params.set("cursor", cursor);
  }
  return requestWithDetail<FallidasPage>(
    `${API_BASE}/api/notificaciones/fallidas?${params.toString()}`,
    isFallidasPage,
    CREDENCIALES,
  );
}

export type { Slot };

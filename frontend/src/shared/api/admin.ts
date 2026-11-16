/**
 * Cliente HTTP de administraci�n (c-13): profesionales, usuarios staff y
 * reporte de ocupaci�n. Guards estrictos por contrato, `credentials: "include"`
 * y reutilizaci�n de `requestWithDetail`/`ApiHttpError` (D-2).
 *
 * El listado p�blico de profesionales no expone `activo`; el admin s�. Cuando
 * el flag `incluir_inactivos` est� apagado se consume el contrato p�blico y se
 * normaliza `activo=true` (el backend solo devuelve activos en esa rama).
 */

import { API_BASE, isRecord, requestWithDetail } from "./client";
import { isProfesionalesResponse } from "./reserva";
import { isStaffRol, type StaffRol } from "./staff";

export interface ProfesionalAdmin {
  id: string;
  nombre: string;
  matricula: string | null;
  especialidad: string | null;
  duracion_default_min: number;
  activo: boolean;
  ultima_actualizacion: string | null;
}

export interface ProfesionalesAdminPage {
  items: ProfesionalAdmin[];
  next_cursor: string | null;
}

export interface ProfesionalCreateInput {
  nombre: string;
  matricula: string | null;
  especialidad: string | null;
  duracion_default_min: number;
}

export interface ProfesionalUpdateInput {
  nombre?: string;
  matricula?: string | null;
  especialidad?: string | null;
  duracion_default_min?: number;
  activo?: boolean;
}

export interface UsuarioStaff {
  id: string;
  email: string;
  rol: StaffRol;
  profesional_id: string | null;
  activo: boolean;
}

export interface UsuariosStaffPage {
  items: UsuarioStaff[];
  next_cursor: string | null;
}

export interface UsuarioStaffCreateInput {
  email: string;
  password: string;
  rol: StaffRol;
  profesional_id?: string | null;
}

export interface UsuarioStaffUpdateInput {
  rol?: StaffRol;
  profesional_id?: string | null;
  activo?: boolean;
}

export interface ReporteProfesional {
  id: string;
  nombre: string;
  activo: boolean;
}

export interface ReporteFila {
  profesional: ReporteProfesional;
  turnos: number;
  atendidos: number;
  ausentes: number;
  cancelados: number;
  pendientes: number;
  minutos_ocupados: number;
  minutos_disponibles: number;
  porcentaje_ocupacion: number | null;
}

export interface ReporteTotales {
  turnos: number;
  atendidos: number;
  ausentes: number;
  cancelados: number;
  pendientes: number;
  minutos_ocupados: number;
  minutos_disponibles: number;
  porcentaje_ocupacion: number | null;
}

export interface ReporteOcupacion {
  desde: string;
  hasta: string;
  zona: string;
  items: ReporteFila[];
  totales: ReporteTotales;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function isProfesionalAdmin(value: unknown): value is ProfesionalAdmin {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string" &&
    isNullableString(value["matricula"]) &&
    isNullableString(value["especialidad"]) &&
    isFiniteNumber(value["duracion_default_min"]) &&
    typeof value["activo"] === "boolean" &&
    isNullableString(value["ultima_actualizacion"])
  );
}

export function isProfesionalesAdminPage(
  value: unknown,
): value is ProfesionalesAdminPage {
  return (
    isRecord(value) &&
    Array.isArray(value["items"]) &&
    value["items"].every(isProfesionalAdmin) &&
    isNullableString(value["next_cursor"])
  );
}

export function isUsuarioStaff(value: unknown): value is UsuarioStaff {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["email"] === "string" &&
    isStaffRol(value["rol"]) &&
    isNullableString(value["profesional_id"]) &&
    typeof value["activo"] === "boolean"
  );
}

export function isUsuariosStaffPage(
  value: unknown,
): value is UsuariosStaffPage {
  return (
    isRecord(value) &&
    Array.isArray(value["items"]) &&
    value["items"].every(isUsuarioStaff) &&
    isNullableString(value["next_cursor"])
  );
}

function isReporteProfesional(value: unknown): value is ReporteProfesional {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["nombre"] === "string" &&
    typeof value["activo"] === "boolean"
  );
}

function isPorcentaje(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
}

function isContadores(value: Record<string, unknown>): boolean {
  return (
    isFiniteNumber(value["turnos"]) &&
    isFiniteNumber(value["atendidos"]) &&
    isFiniteNumber(value["ausentes"]) &&
    isFiniteNumber(value["cancelados"]) &&
    isFiniteNumber(value["pendientes"]) &&
    isFiniteNumber(value["minutos_ocupados"]) &&
    isFiniteNumber(value["minutos_disponibles"])
  );
}

export function isReporteFila(value: unknown): value is ReporteFila {
  return (
    isRecord(value) &&
    isReporteProfesional(value["profesional"]) &&
    isContadores(value) &&
    isPorcentaje(value["porcentaje_ocupacion"])
  );
}

export function isReporteTotales(value: unknown): value is ReporteTotales {
  return (
    isRecord(value) &&
    isContadores(value) &&
    isPorcentaje(value["porcentaje_ocupacion"])
  );
}

export function isReporteOcupacion(
  value: unknown,
): value is ReporteOcupacion {
  return (
    isRecord(value) &&
    typeof value["desde"] === "string" &&
    typeof value["hasta"] === "string" &&
    typeof value["zona"] === "string" &&
    Array.isArray(value["items"]) &&
    value["items"].every(isReporteFila) &&
    isReporteTotales(value["totales"])
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

function queryDe(params: URLSearchParams): string {
  const query = params.toString();
  return query === "" ? "" : `?${query}`;
}

/**
 * Listado administrativo completo: recorre el keyset hasta `next_cursor=null`
 * (D-4). Con el flag encendido usa el contrato admin (expone `activo`); con el
 * flag apagado consume el contrato p�blico y normaliza `activo=true`.
 */
export async function listarProfesionalesAdmin(
  incluirInactivos: boolean,
): Promise<ProfesionalAdmin[]> {
  const items: ProfesionalAdmin[] = [];
  let cursor: string | null = null;
  do {
    const params = new URLSearchParams();
    if (incluirInactivos) {
      params.set("incluir_inactivos", "true");
    }
    if (cursor !== null) {
      params.set("cursor", cursor);
    }
    const url = `${API_BASE}/api/profesionales${queryDe(params)}`;
    if (incluirInactivos) {
      const page = await requestWithDetail<ProfesionalesAdminPage>(
        url,
        isProfesionalesAdminPage,
        CREDENCIALES,
      );
      items.push(...page.items);
      cursor = page.next_cursor;
    } else {
      const page = await requestWithDetail(
        url,
        isProfesionalesResponse,
        CREDENCIALES,
      );
      items.push(...page.items.map((item) => ({ ...item, activo: true })));
      cursor = page.next_cursor;
    }
  } while (cursor !== null);
  return items;
}

export function crearProfesional(
  body: ProfesionalCreateInput,
): Promise<ProfesionalAdmin> {
  return requestWithDetail<ProfesionalAdmin>(
    `${API_BASE}/api/profesionales`,
    isProfesionalAdmin,
    jsonInit("POST", body),
  );
}

export function actualizarProfesional(
  id: string,
  body: ProfesionalUpdateInput,
): Promise<ProfesionalAdmin> {
  return requestWithDetail<ProfesionalAdmin>(
    `${API_BASE}/api/profesionales/${encodeURIComponent(id)}`,
    isProfesionalAdmin,
    jsonInit("PUT", body),
  );
}

export function darDeBajaProfesional(id: string): Promise<ProfesionalAdmin> {
  return requestWithDetail<ProfesionalAdmin>(
    `${API_BASE}/api/profesionales/${encodeURIComponent(id)}`,
    isProfesionalAdmin,
    { ...CREDENCIALES, method: "DELETE" },
  );
}

export function listarUsuariosStaff(
  limit = 20,
  cursor?: string,
): Promise<UsuariosStaffPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) {
    params.set("cursor", cursor);
  }
  return requestWithDetail<UsuariosStaffPage>(
    `${API_BASE}/api/usuarios-staff${queryDe(params)}`,
    isUsuariosStaffPage,
    CREDENCIALES,
  );
}

function bodyUsuario(
  body: UsuarioStaffCreateInput,
): Record<string, string> {
  const payload: Record<string, string> = {
    email: body.email,
    password: body.password,
    rol: body.rol,
  };
  if (body.profesional_id !== undefined && body.profesional_id !== null) {
    payload["profesional_id"] = body.profesional_id;
  }
  return payload;
}

export function crearUsuarioStaff(
  body: UsuarioStaffCreateInput,
): Promise<UsuarioStaff> {
  return requestWithDetail<UsuarioStaff>(
    `${API_BASE}/api/usuarios-staff`,
    isUsuarioStaff,
    jsonInit("POST", bodyUsuario(body)),
  );
}

export function actualizarUsuarioStaff(
  id: string,
  body: UsuarioStaffUpdateInput,
): Promise<UsuarioStaff> {
  return requestWithDetail<UsuarioStaff>(
    `${API_BASE}/api/usuarios-staff/${encodeURIComponent(id)}`,
    isUsuarioStaff,
    jsonInit("PUT", body),
  );
}

export function darDeBajaUsuarioStaff(id: string): Promise<UsuarioStaff> {
  return requestWithDetail<UsuarioStaff>(
    `${API_BASE}/api/usuarios-staff/${encodeURIComponent(id)}`,
    isUsuarioStaff,
    { ...CREDENCIALES, method: "DELETE" },
  );
}

export function getReporteOcupacion(
  desde: string,
  hasta: string,
  profesionalId?: string,
): Promise<ReporteOcupacion> {
  const params = new URLSearchParams({ desde, hasta });
  if (profesionalId !== undefined) {
    params.set("profesional_id", profesionalId);
  }
  return requestWithDetail<ReporteOcupacion>(
    `${API_BASE}/api/reportes/ocupacion${queryDe(params)}`,
    isReporteOcupacion,
    CREDENCIALES,
  );
}

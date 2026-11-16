/**
 * Acciones de turno permitidas por estado y rol (RN-TU-07, D-9): solo
 * recepción/admin reprograman o cancelan, y solo turnos `reservado`/`confirmado`.
 * Las transiciones de estado salen de la matriz cerrada y `ausente` queda
 * reservado a recepción/admin.
 */

import type { StaffRol } from "../../../shared/api/staff";

const ESTADOS_ACTIVOS: readonly string[] = ["reservado", "confirmado"];

const ROLES_OPERADORES: readonly StaffRol[] = ["recepcion", "admin"];

export type TransicionEstado = "confirmado" | "atendido" | "ausente";

export interface TransicionPermitida {
  estado: TransicionEstado;
  etiqueta: string;
}

export function puedeOperarTurno(rol: StaffRol): boolean {
  return ROLES_OPERADORES.includes(rol);
}

export function puedeReprogramar(estado: string, rol: StaffRol): boolean {
  return puedeOperarTurno(rol) && ESTADOS_ACTIVOS.includes(estado);
}

export function puedeCancelar(estado: string, rol: StaffRol): boolean {
  return puedeOperarTurno(rol) && ESTADOS_ACTIVOS.includes(estado);
}

export function puedeCorregirPaciente(rol: StaffRol): boolean {
  return puedeOperarTurno(rol);
}

export function transicionesPermitidas(
  estado: string,
  rol: StaffRol,
): TransicionPermitida[] {
  if (estado === "reservado") {
    return [{ estado: "confirmado", etiqueta: "Marcar confirmado" }];
  }
  if (estado === "confirmado") {
    const transiciones: TransicionPermitida[] = [
      { estado: "atendido", etiqueta: "Marcar atendido" },
    ];
    if (puedeOperarTurno(rol)) {
      transiciones.push({ estado: "ausente", etiqueta: "Marcar ausente" });
    }
    return transiciones;
  }
  return [];
}

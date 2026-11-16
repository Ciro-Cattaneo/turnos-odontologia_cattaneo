/**
 * Gating de pantalla admin (D-1, D-9): deriva `esAdmin` de la sesión ya
 * resuelta por `StaffLayout`, sin una segunda llamada a `/api/auth/me`.
 */

import type { MeOut } from "../../../shared/api/staff";
import { useExpirarSesion, useStaffSesion } from "../sesion";

export interface SesionAdmin {
  esAdmin: boolean;
  sesion: MeOut;
  expirarSesion: () => void;
}

export function useSesionAdmin(): SesionAdmin {
  const sesion = useStaffSesion();
  const expirarSesion = useExpirarSesion();
  return {
    esAdmin: sesion.rol === "admin",
    sesion,
    expirarSesion,
  };
}

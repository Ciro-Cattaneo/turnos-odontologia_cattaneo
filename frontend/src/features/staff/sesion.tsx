/**
 * Contexto acotado de sesión staff (`email`, `rol`, `profesional_id`) y acción
 * de expiración compartida con las pantallas (D-3).
 */

import { createContext, useContext, type ReactNode } from "react";

import { isRecord } from "../../shared/api/client";
import type { MeOut } from "../../shared/api/staff";

export const AVISO_SESION_EXPIRADA =
  "Tu sesión expiró. Volvé a iniciar sesión.";

export type AvisoSesion = "sesion_expirada";

const SesionContext = createContext<MeOut | null>(null);
const ExpirarContext = createContext<(() => void) | null>(null);

interface StaffSesionProviderProps {
  sesion: MeOut;
  onExpirar: () => void;
  children: ReactNode;
}

export function StaffSesionProvider({
  sesion,
  onExpirar,
  children,
}: StaffSesionProviderProps): JSX.Element {
  return (
    <ExpirarContext.Provider value={onExpirar}>
      <SesionContext.Provider value={sesion}>{children}</SesionContext.Provider>
    </ExpirarContext.Provider>
  );
}

export function useStaffSesion(): MeOut {
  const sesion = useContext(SesionContext);
  if (sesion === null) {
    throw new Error("useStaffSesion fuera de StaffLayout");
  }
  return sesion;
}

export function useExpirarSesion(): () => void {
  const expirar = useContext(ExpirarContext);
  if (expirar === null) {
    throw new Error("useExpirarSesion fuera de StaffLayout");
  }
  return expirar;
}

/** Lee el aviso de sesión desde el `state` del router (nunca desde la URL). */
export function avisoDeEstado(state: unknown): AvisoSesion | null {
  if (isRecord(state) && state["aviso"] === "sesion_expirada") {
    return "sesion_expirada";
  }
  return null;
}

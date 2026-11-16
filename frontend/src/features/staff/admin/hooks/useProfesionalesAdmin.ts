/**
 * Estado del listado admin de profesionales (D-7): flag `incluir_inactivos`,
 * carga inicial, reintento y reemplazo local tras una mutación. El 401 se
 * traduce a la expiración de sesión compartida.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiHttpError } from "../../../../shared/api/client";
import {
  listarProfesionalesAdmin,
  type ProfesionalAdmin,
} from "../../../../shared/api/admin";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import { useExpirarSesion } from "../../sesion";

export type EstadoProfesionales = "cargando" | "listo" | "error";

export interface ProfesionalesAdminState {
  estado: EstadoProfesionales;
  items: ProfesionalAdmin[];
  error: StaffErrorInfo | null;
  incluirInactivos: boolean;
  cambiarIncluirInactivos: (valor: boolean) => void;
  refrescar: () => Promise<void>;
  reemplazar: (item: ProfesionalAdmin) => void;
}

export function useProfesionalesAdmin(): ProfesionalesAdminState {
  const expirarSesion = useExpirarSesion();
  const [incluirInactivos, setIncluirInactivos] = useState(true);
  const [items, setItems] = useState<ProfesionalAdmin[]>([]);
  const [estado, setEstado] = useState<EstadoProfesionales>("cargando");
  const [error, setError] = useState<StaffErrorInfo | null>(null);

  const cargar = useCallback(async (): Promise<void> => {
    setEstado("cargando");
    setError(null);
    try {
      const lista = await listarProfesionalesAdmin(incluirInactivos);
      setItems(lista);
      setEstado("listo");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el listado de profesionales"));
      setEstado("error");
    }
  }, [incluirInactivos, expirarSesion]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const cambiarIncluirInactivos = useCallback((valor: boolean): void => {
    setIncluirInactivos(valor);
  }, []);

  const reemplazar = useCallback((item: ProfesionalAdmin): void => {
    setItems((previos) =>
      previos.map((previo) => (previo.id === item.id ? item : previo)),
    );
  }, []);

  return {
    estado,
    items,
    error,
    incluirInactivos,
    cambiarIncluirInactivos,
    refrescar: cargar,
    reemplazar,
  };
}

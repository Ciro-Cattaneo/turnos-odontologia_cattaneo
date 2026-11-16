/**
 * Estado del listado admin de usuarios staff (D-4/D-7): primera página con
 * `limit=20`, "Cargar más" por cursor opaco deduplicando por `id` y catálogo
 * de profesionales activos cargado en paralelo para el selector (D-7).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiHttpError } from "../../../../shared/api/client";
import {
  listarProfesionalesAdmin,
  listarUsuariosStaff,
  type ProfesionalAdmin,
  type UsuarioStaff,
} from "../../../../shared/api/admin";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import { useExpirarSesion } from "../../sesion";

export type EstadoUsuariosStaff = "cargando" | "listo" | "error";

export interface UsuariosStaffAdminState {
  estado: EstadoUsuariosStaff;
  items: UsuarioStaff[];
  profesionales: ProfesionalAdmin[];
  error: StaffErrorInfo | null;
  nextCursor: string | null;
  cargandoMas: boolean;
  refrescar: () => Promise<void>;
  cargarMas: () => Promise<void>;
  reemplazar: (item: UsuarioStaff) => void;
}

function deduplicar(items: UsuarioStaff[]): UsuarioStaff[] {
  const vistos = new Set<string>();
  const unicos: UsuarioStaff[] = [];
  for (const item of items) {
    if (vistos.has(item.id)) {
      continue;
    }
    vistos.add(item.id);
    unicos.push(item);
  }
  return unicos;
}

export function useUsuariosStaffAdmin(): UsuariosStaffAdminState {
  const expirarSesion = useExpirarSesion();
  const [items, setItems] = useState<UsuarioStaff[]>([]);
  const [profesionales, setProfesionales] = useState<ProfesionalAdmin[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [estado, setEstado] = useState<EstadoUsuariosStaff>("cargando");
  const [cargandoMas, setCargandoMas] = useState(false);
  const [error, setError] = useState<StaffErrorInfo | null>(null);

  const cargar = useCallback(async (): Promise<void> => {
    setEstado("cargando");
    setError(null);
    try {
      const [page, listaProfesionales] = await Promise.all([
        listarUsuariosStaff(20),
        listarProfesionalesAdmin(false),
      ]);
      setItems(deduplicar(page.items));
      setNextCursor(page.next_cursor);
      setProfesionales(listaProfesionales);
      setEstado("listo");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el listado de usuarios staff"));
      setEstado("error");
    }
  }, [expirarSesion]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const cargarMas = useCallback(async (): Promise<void> => {
    if (nextCursor === null || cargandoMas) {
      return;
    }
    setCargandoMas(true);
    setError(null);
    try {
      const page = await listarUsuariosStaff(20, nextCursor);
      setItems((previos) => deduplicar([...previos, ...page.items]));
      setNextCursor(page.next_cursor);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el listado de usuarios staff"));
    } finally {
      setCargandoMas(false);
    }
  }, [nextCursor, cargandoMas, expirarSesion]);

  const reemplazar = useCallback((item: UsuarioStaff): void => {
    setItems((previos) =>
      previos.map((previo) => (previo.id === item.id ? item : previo)),
    );
  }, []);

  return {
    estado,
    items,
    profesionales,
    error,
    nextCursor,
    cargandoMas,
    refrescar: cargar,
    cargarMas,
    reemplazar,
  };
}

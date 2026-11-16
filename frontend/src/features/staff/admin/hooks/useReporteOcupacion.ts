/**
 * Estado del reporte de ocupación (D-7): carga inicial con el rango por
 * defecto y el catálogo de profesionales en paralelo (`Promise.all`), consulta
 * explícita con el filtro elegido y `401` traducido a expiración de sesión.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiHttpError } from "../../../../shared/api/client";
import {
  getReporteOcupacion,
  listarProfesionalesAdmin,
  type ProfesionalAdmin,
  type ReporteOcupacion,
} from "../../../../shared/api/admin";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import { useExpirarSesion } from "../../sesion";
import { rangoPorDefecto } from "../rango";

export type EstadoReporte = "cargando" | "listo" | "error";

export interface ReporteOcupacionState {
  estado: EstadoReporte;
  reporte: ReporteOcupacion | null;
  profesionales: ProfesionalAdmin[];
  error: StaffErrorInfo | null;
  desde: string;
  hasta: string;
  profesionalId: string;
  cambiarDesde: (valor: string) => void;
  cambiarHasta: (valor: string) => void;
  cambiarProfesional: (valor: string) => void;
  consultar: () => Promise<void>;
  reintentar: () => Promise<void>;
}

export function useReporteOcupacion(): ReporteOcupacionState {
  const expirarSesion = useExpirarSesion();
  const [rangoInicial] = useState(rangoPorDefecto);
  const [desde, setDesde] = useState(rangoInicial.desde);
  const [hasta, setHasta] = useState(rangoInicial.hasta);
  const [profesionalId, setProfesionalId] = useState("");
  const [reporte, setReporte] = useState<ReporteOcupacion | null>(null);
  const [profesionales, setProfesionales] = useState<ProfesionalAdmin[]>([]);
  const [estado, setEstado] = useState<EstadoReporte>("cargando");
  const [error, setError] = useState<StaffErrorInfo | null>(null);

  const cargarInicial = useCallback(async (): Promise<void> => {
    setEstado("cargando");
    setError(null);
    try {
      const [datos, catalogo] = await Promise.all([
        getReporteOcupacion(rangoInicial.desde, rangoInicial.hasta),
        listarProfesionalesAdmin(true),
      ]);
      setReporte(datos);
      setProfesionales(catalogo);
      setEstado("listo");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el reporte de ocupación"));
      setReporte(null);
      setEstado("error");
    }
  }, [expirarSesion, rangoInicial]);

  useEffect(() => {
    void cargarInicial();
  }, [cargarInicial]);

  const consultar = useCallback(async (): Promise<void> => {
    setEstado("cargando");
    setError(null);
    try {
      const datos = await getReporteOcupacion(
        desde,
        hasta,
        profesionalId === "" ? undefined : profesionalId,
      );
      setReporte(datos);
      setEstado("listo");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el reporte de ocupación"));
      setReporte(null);
      setEstado("error");
    }
  }, [desde, hasta, profesionalId, expirarSesion]);

  return {
    estado,
    reporte,
    profesionales,
    error,
    desde,
    hasta,
    profesionalId,
    cambiarDesde: setDesde,
    cambiarHasta: setHasta,
    cambiarProfesional: setProfesionalId,
    consultar,
    reintentar: consultar,
  };
}

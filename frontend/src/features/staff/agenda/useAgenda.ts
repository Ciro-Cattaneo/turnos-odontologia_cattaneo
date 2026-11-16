/**
 * Agenda staff con cache por `profesionalId|vista|fecha`: cambiar de
 * profesional o volver a una clave ya cargada no re-consulta; "Actualizar"
 * fuerza una recarga de la clave visible (D-5).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, ApiHttpError } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import {
  getAgenda,
  type AgendaResponse,
  type VistaAgenda,
} from "../../../shared/api/staff";
import { useExpirarSesion } from "../sesion";

export type AgendaStatus = "idle" | "loading" | "success" | "error";

export type AgendaErrorKind = "network" | "http" | "invalid";

export interface AgendaEstado {
  status: AgendaStatus;
  agenda: AgendaResponse | null;
  error: StaffErrorInfo | null;
  errorKind: AgendaErrorKind | null;
}

const ESTADO_IDLE: AgendaEstado = {
  status: "idle",
  agenda: null,
  error: null,
  errorKind: null,
};

export function claveAgenda(
  profesionalId: string,
  vista: VistaAgenda,
  fecha: string,
): string {
  return `${profesionalId}|${vista}|${fecha}`;
}

function clasificarError(error: unknown): AgendaErrorKind {
  if (error instanceof ApiHttpError) {
    return "http";
  }
  if (error instanceof ApiError && error.code === "NETWORK_ERROR") {
    return "network";
  }
  return "invalid";
}

interface ParametrosAgenda {
  profesionalId: string | null;
  vista: VistaAgenda;
  fecha: string;
}

export interface UseAgenda {
  estado: AgendaEstado;
  actualizar: () => void;
  reintentar: () => void;
  invalidar: (profesionalId: string, vista: VistaAgenda, fecha: string) => void;
}

export function useAgenda({
  profesionalId,
  vista,
  fecha,
}: ParametrosAgenda): UseAgenda {
  const expirarSesion = useExpirarSesion();
  const cache = useRef<Map<string, AgendaEstado>>(new Map());
  const enVuelo = useRef<Set<string>>(new Set());
  const claveActual = useRef<string | null>(null);
  const forzar = useRef(false);
  const [estado, setEstado] = useState<AgendaEstado>(ESTADO_IDLE);
  const [refresco, setRefresco] = useState(0);

  const clave =
    profesionalId === null ? null : claveAgenda(profesionalId, vista, fecha);

  const cargar = useCallback(
    async (
      clavePedida: string,
      idPedido: string,
      vistaPedida: VistaAgenda,
      fechaPedida: string,
      ignorarCache: boolean,
    ): Promise<void> => {
      if (!ignorarCache) {
        const cacheado = cache.current.get(clavePedida);
        if (cacheado !== undefined && cacheado.status === "success") {
          if (claveActual.current === clavePedida) {
            setEstado(cacheado);
          }
          return;
        }
      }
      if (enVuelo.current.has(clavePedida)) {
        return;
      }
      enVuelo.current.add(clavePedida);
      const cargando: AgendaEstado = {
        status: "loading",
        agenda: null,
        error: null,
        errorKind: null,
      };
      cache.current.set(clavePedida, cargando);
      if (claveActual.current === clavePedida) {
        setEstado(cargando);
      }
      try {
        const agenda = await getAgenda(idPedido, vistaPedida, fechaPedida);
        const exito: AgendaEstado = {
          status: "success",
          agenda,
          error: null,
          errorKind: null,
        };
        cache.current.set(clavePedida, exito);
        if (claveActual.current === clavePedida) {
          setEstado(exito);
        }
      } catch (err: unknown) {
        if (err instanceof ApiHttpError && err.status === 401) {
          cache.current.delete(clavePedida);
          expirarSesion();
          return;
        }
        const fallo: AgendaEstado = {
          status: "error",
          agenda: null,
          error: mensajeDeError(err, "la agenda"),
          errorKind: clasificarError(err),
        };
        cache.current.set(clavePedida, fallo);
        if (claveActual.current === clavePedida) {
          setEstado(fallo);
        }
      } finally {
        enVuelo.current.delete(clavePedida);
      }
    },
    [expirarSesion],
  );

  useEffect(() => {
    claveActual.current = clave;
    if (clave === null || profesionalId === null) {
      forzar.current = false;
      setEstado(ESTADO_IDLE);
      return;
    }
    const ignorarCache = forzar.current;
    forzar.current = false;
    const cacheado = cache.current.get(clave);
    if (!ignorarCache && cacheado !== undefined) {
      setEstado(cacheado);
      return;
    }
    void cargar(clave, profesionalId, vista, fecha, ignorarCache);
  }, [clave, refresco, cargar, profesionalId, vista, fecha]);

  const actualizar = useCallback(() => {
    forzar.current = true;
    setRefresco((valor) => valor + 1);
  }, []);

  const invalidar = useCallback(
    (profesionalId: string, vista: VistaAgenda, fecha: string): void => {
      cache.current.delete(claveAgenda(profesionalId, vista, fecha));
    },
    [],
  );

  return { estado, actualizar, reintentar: actualizar, invalidar };
}

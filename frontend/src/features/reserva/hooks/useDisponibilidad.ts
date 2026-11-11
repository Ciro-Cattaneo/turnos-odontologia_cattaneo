/** Estado local de la consulta de disponibilidad (D-5, D-9). */

import { useCallback, useRef, useState } from "react";

import { getDisponibilidadDia } from "../../../shared/api/reserva";
import { describirError } from "../errores";
import type { DisponibilidadState } from "../types";

const ESTADO_INICIAL: DisponibilidadState = {
  status: "idle",
  slots: [],
  error: null,
};

interface UltimaBusqueda {
  profesionalId: string;
  fecha: string;
}

export interface UseDisponibilidad {
  state: DisponibilidadState;
  buscar: (profesionalId: string, fecha: string) => Promise<void>;
  reintentar: () => void;
  reiniciar: () => void;
}

export function useDisponibilidad(): UseDisponibilidad {
  const [state, setState] = useState<DisponibilidadState>(ESTADO_INICIAL);
  const ultima = useRef<UltimaBusqueda | null>(null);

  const buscar = useCallback(async (profesionalId: string, fecha: string) => {
    ultima.current = { profesionalId, fecha };
    setState({ status: "loading", slots: [], error: null });
    try {
      const response = await getDisponibilidadDia(profesionalId, fecha);
      if (response.slots.length === 0) {
        setState({ status: "empty", slots: [], error: null });
      } else {
        setState({ status: "success", slots: response.slots, error: null });
      }
    } catch (err: unknown) {
      setState({ status: "error", slots: [], error: describirError(err) });
    }
  }, []);

  const reintentar = useCallback(() => {
    const busqueda = ultima.current;
    if (busqueda !== null) {
      void buscar(busqueda.profesionalId, busqueda.fecha);
    }
  }, [buscar]);

  const reiniciar = useCallback(() => {
    ultima.current = null;
    setState(ESTADO_INICIAL);
  }, []);

  return { state, buscar, reintentar, reiniciar };
}

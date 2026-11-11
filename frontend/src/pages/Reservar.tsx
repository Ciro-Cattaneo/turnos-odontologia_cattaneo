/** Página pública `/reservar`: búsqueda, formulario y resumen en una sola URL (D-2). */

import { useCallback, useEffect, useState } from "react";

import {
  ApiHttpError,
  isAlternativosDetail,
  type ApiErrorDetail,
  type Slot,
} from "../shared/api/client";
import {
  crearTurno,
  getProfesionales,
  type CrearTurnoBody,
  type Profesional,
  type TurnoOut,
} from "../shared/api/reserva";
import { AlternativosList } from "../features/reserva/components/AlternativosList";
import { FechaSelector } from "../features/reserva/components/FechaSelector";
import { ProfesionalSelector } from "../features/reserva/components/ProfesionalSelector";
import { ReservaForm } from "../features/reserva/components/ReservaForm";
import { ReservaResumen } from "../features/reserva/components/ReservaResumen";
import { SlotList } from "../features/reserva/components/SlotList";
import { describirError } from "../features/reserva/errores";
import { useDisponibilidad } from "../features/reserva/hooks/useDisponibilidad";
import type { BusquedaError, FormValues } from "../features/reserva/types";
import styles from "./Reservar.module.css";

type ProfesionalesStatus = "loading" | "success" | "empty" | "error";

type FormStatus = "idle" | "submitting" | "done";

export function Reservar(): JSX.Element {
  const [profesionales, setProfesionales] = useState<Profesional[]>([]);
  const [profesionalesStatus, setProfesionalesStatus] =
    useState<ProfesionalesStatus>("loading");
  const [profesionalesError, setProfesionalesError] =
    useState<BusquedaError | null>(null);

  const [profesionalId, setProfesionalId] = useState("");
  const [fecha, setFecha] = useState("");
  const { state: disponibilidad, buscar, reintentar, reiniciar } =
    useDisponibilidad();

  const [slot, setSlot] = useState<Slot | null>(null);
  const [serverDetail, setServerDetail] = useState<ApiErrorDetail | null>(null);
  const [alternativos, setAlternativos] = useState<Slot[] | null>(null);
  const [reservaError, setReservaError] = useState<BusquedaError | null>(null);
  const [noDisponible, setNoDisponible] = useState(false);
  const [formStatus, setFormStatus] = useState<FormStatus>("idle");
  const [resultado, setResultado] = useState<TurnoOut | null>(null);

  const limpiarResultado = useCallback(() => {
    setServerDetail(null);
    setAlternativos(null);
    setReservaError(null);
    setNoDisponible(false);
  }, []);

  const cargarProfesionales = useCallback(async () => {
    setProfesionalesStatus("loading");
    setProfesionalesError(null);
    try {
      const items = await getProfesionales();
      setProfesionales(items);
      setProfesionalesStatus(items.length === 0 ? "empty" : "success");
    } catch (err: unknown) {
      setProfesionalesStatus("error");
      setProfesionalesError(describirError(err));
    }
  }, []);

  useEffect(() => {
    void cargarProfesionales();
  }, [cargarProfesionales]);

  const reiniciarBusqueda = useCallback(() => {
    reiniciar();
    setSlot(null);
    limpiarResultado();
  }, [limpiarResultado, reiniciar]);

  const cambiarProfesional = (id: string): void => {
    setProfesionalId(id);
    reiniciarBusqueda();
  };

  const cambiarFecha = (valor: string): void => {
    setFecha(valor);
    reiniciarBusqueda();
  };

  const buscarHorarios = (): void => {
    if (profesionalId === "" || fecha === "") {
      return;
    }
    setSlot(null);
    limpiarResultado();
    void buscar(profesionalId, fecha);
  };

  const seleccionarSlot = (nuevo: Slot): void => {
    setSlot(nuevo);
    limpiarResultado();
  };

  const recargarProfesionales = (): void => {
    setProfesionalId("");
    setFecha("");
    setSlot(null);
    reiniciarBusqueda();
    void cargarProfesionales();
  };

  const reservar = async (values: FormValues): Promise<void> => {
    if (slot === null) {
      return;
    }
    setFormStatus("submitting");
    limpiarResultado();
    const body: CrearTurnoBody = {
      profesional_id: profesionalId,
      inicio: slot.inicio,
      duracion_min: slot.duracion_min,
      paciente: values,
    };
    try {
      const turno = await crearTurno(body);
      setResultado(turno);
      setFormStatus("done");
    } catch (err: unknown) {
      setFormStatus("idle");
      if (err instanceof ApiHttpError) {
        if (err.status === 400) {
          setServerDetail(err.detail);
          return;
        }
        if (err.status === 409) {
          if (isAlternativosDetail(err.detail)) {
            setAlternativos(err.detail.alternativos);
          } else {
            setAlternativos([]);
          }
          return;
        }
        if (err.status === 404) {
          setNoDisponible(true);
          setReservaError(describirError(err));
          return;
        }
      }
      setReservaError(describirError(err));
    }
  };

  if (resultado !== null) {
    return (
      <main className={styles.pagina}>
        <h1 className={styles.titulo}>Reservar turno</h1>
        <ReservaResumen turno={resultado} />
      </main>
    );
  }

  const buscando = disponibilidad.status === "loading";
  const puedeBuscar = profesionalId !== "" && fecha !== "" && !buscando;

  return (
    <main className={styles.pagina}>
      <h1 className={styles.titulo}>Reservar turno</h1>

      {profesionalesStatus === "loading" && (
        <p className={styles.estado} role="status">
          Cargando profesionales…
        </p>
      )}

      {profesionalesStatus === "error" && profesionalesError !== null && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{profesionalesError.message}</p>
          <button
            type="button"
            className={styles.botonSecundario}
            onClick={() => {
              void cargarProfesionales();
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {profesionalesStatus === "empty" && (
        <p className={styles.estado} role="status">
          No hay profesionales disponibles en este momento. Volvé a intentarlo
          más tarde.
        </p>
      )}

      {profesionalesStatus === "success" && (
        <section className={styles.busqueda} aria-label="Buscar horarios">
          <ProfesionalSelector
            profesionales={profesionales}
            value={profesionalId}
            onChange={cambiarProfesional}
            disabled={buscando}
          />
          <FechaSelector
            value={fecha}
            onChange={cambiarFecha}
            disabled={buscando}
          />
          <button
            type="button"
            className={styles.boton}
            disabled={!puedeBuscar}
            onClick={buscarHorarios}
          >
            Buscar horarios
          </button>
        </section>
      )}

      {disponibilidad.status === "loading" && (
        <p className={styles.estado} role="status">
          Cargando horarios…
        </p>
      )}

      {disponibilidad.status === "empty" && (
        <p className={styles.estado} role="status">
          No hay horarios disponibles para esa fecha. Probá con otra fecha.
        </p>
      )}

      {disponibilidad.status === "error" && disponibilidad.error !== null && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{disponibilidad.error.message}</p>
          {disponibilidad.error.kind === "no_disponible" && (
            <button
              type="button"
              className={styles.botonSecundario}
              onClick={recargarProfesionales}
            >
              Recargar profesionales
            </button>
          )}
          {(disponibilidad.error.kind === "network" ||
            disponibilidad.error.kind === "unexpected") && (
            <button
              type="button"
              className={styles.botonSecundario}
              onClick={reintentar}
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {disponibilidad.status === "success" && (
        <SlotList
          slots={disponibilidad.slots}
          onSelect={seleccionarSlot}
          seleccionado={slot?.inicio ?? null}
        />
      )}

      {alternativos !== null && (
        <AlternativosList
          alternativos={alternativos}
          onSelect={seleccionarSlot}
          disabled={formStatus === "submitting"}
        />
      )}

      {noDisponible && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>
            El profesional ya no está disponible. Recargá la lista o elegí otro
            profesional; tus datos siguen cargados.
          </p>
          <button
            type="button"
            className={styles.botonSecundario}
            onClick={recargarProfesionales}
          >
            Recargar profesionales
          </button>
        </div>
      )}

      {reservaError !== null && (
        <p className={styles.alertaTexto} role="alert">
          {reservaError.message}
        </p>
      )}

      {slot !== null && (
        <ReservaForm
          slot={slot}
          submitting={formStatus === "submitting"}
          serverDetail={serverDetail}
          onSubmit={(values) => {
            void reservar(values);
          }}
        />
      )}
    </main>
  );
}

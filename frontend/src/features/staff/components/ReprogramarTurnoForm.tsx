/**
 * Reprogramación de un turno: fecha destino, franjas libres del mismo
 * profesional y duración múltiplo de la granularidad (D-10, RN-TU-02/03).
 */

import { useEffect, useMemo, useState, type FormEvent } from "react";

import { ApiHttpError, type Slot } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import {
  reprogramar,
  type FranjaLibre,
  type FranjaStaff,
  type ReprogramacionOut,
  type TurnoFichaOut,
} from "../../../shared/api/staff";
import {
  fechaEnConsultorio,
  formatearDuracion,
  formatearHora,
} from "../../../shared/format";
import { AlternativosList } from "../../reserva/components/AlternativosList";
import { esDuracionValida, opcionesDuracion } from "../agenda/duracion";
import { useAgenda } from "../agenda/useAgenda";
import { useExpirarSesion } from "../sesion";
import styles from "./OperacionTurno.module.css";

interface ReprogramarTurnoFormProps {
  turnoId: string;
  profesionalId: string;
  granularidad: number;
  ficha: TurnoFichaOut;
  onReprogramado: (out: ReprogramacionOut) => Promise<void>;
  onNoEditable: (mensaje: string) => Promise<void>;
  onCancelar: () => void;
}

function franjasLibres(franjas: FranjaStaff[]): FranjaLibre[] {
  return franjas.filter((franja): franja is FranjaLibre => franja.tipo === "libre");
}

export function ReprogramarTurnoForm({
  turnoId,
  profesionalId,
  granularidad,
  ficha,
  onReprogramado,
  onNoEditable,
  onCancelar,
}: ReprogramarTurnoFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const fechaTurno = fechaEnConsultorio(new Date(ficha.inicio));
  const [fecha, setFecha] = useState<string>(fechaTurno);
  const [inicio, setInicio] = useState<string>(ficha.inicio);
  const [duracionMin, setDuracionMin] = useState<number>(ficha.duracion_min);
  const [alternativo, setAlternativo] = useState<Slot | null>(null);
  const [localInicio, setLocalInicio] = useState<string | null>(null);
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [alternativos, setAlternativos] = useState<Slot[]>([]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (info === null || info.kind !== "field") {
      return;
    }
    if (info.fieldErrors["inicio"] !== undefined) {
      document.getElementById("repro-inicio")?.focus();
    } else if (info.fieldErrors["duracion_min"] !== undefined) {
      document.getElementById("repro-duracion")?.focus();
    }
  }, [info]);

  const agenda = useAgenda({ profesionalId, vista: "dia", fecha });
  const opciones = useMemo(() => opcionesDuracion(granularidad), [granularidad]);

  const libres: FranjaLibre[] =
    agenda.estado.status === "success" && agenda.estado.agenda !== null
      ? franjasLibres(agenda.estado.agenda.dias[0]?.franjas ?? [])
      : [];

  const errorInicio =
    localInicio ??
    (info !== null && info.kind === "field"
      ? (info.fieldErrors["inicio"] ?? null)
      : null);
  const errorDuracion =
    info !== null && info.kind === "field"
      ? (info.fieldErrors["duracion_min"] ?? null)
      : null;

  const cambiarFecha = (nueva: string): void => {
    setFecha(nueva);
    setInicio(nueva === fechaTurno ? ficha.inicio : "");
    setAlternativo(null);
    setLocalInicio(null);
    setInfo(null);
    setAlternativos([]);
  };

  const elegirSlot = (nuevoInicio: string): void => {
    setInicio(nuevoInicio);
    setLocalInicio(null);
  };

  const elegirAlternativo = (slot: Slot): void => {
    setAlternativo(slot);
    setInicio(slot.inicio);
    setDuracionMin(slot.duracion_min);
    setAlternativos([]);
    setInfo(null);
  };

  const enviar = async (): Promise<void> => {
    setPending(true);
    setInfo(null);
    setAlternativos([]);
    try {
      const out = await reprogramar(turnoId, {
        inicio,
        duracion_min: duracionMin,
      });
      await onReprogramado(out);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "la reprogramación");
      if (error.kind === "validation" && error.codigo === "turno_no_editable") {
        await onNoEditable(error.message);
        return;
      }
      setInfo(error);
      setAlternativos(error.alternativos);
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (inicio === "") {
      setLocalInicio("Elegí un horario libre del día destino.");
      document.getElementById("repro-inicio")?.focus();
      return;
    }
    if (!esDuracionValida(duracionMin, granularidad)) {
      setLocalInicio(null);
      setInfo({
        kind: "field",
        message: "Revisá los datos marcados.",
        fieldErrors: {
          duracion_min: `La duración debe ser múltiplo de ${granularidad} min.`,
        },
        alternativos: [],
        codigo: null,
      });
      document.getElementById("repro-duracion")?.focus();
      return;
    }
    void enviar();
  };

  const opcionActual = fecha === fechaTurno ? ficha.inicio : null;
  const opcionAlternativa =
    alternativo !== null && alternativo.inicio === inicio
      ? alternativo
      : null;

  return (
    <form
      className={styles.formulario}
      aria-label="Reprogramar turno"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h3 className={styles.titulo}>Reprogramar turno</h3>
        <button
          type="button"
          className={styles.secundario}
          disabled={pending}
          onClick={onCancelar}
        >
          Volver
        </button>
      </div>

      {info !== null && (
        <p className={styles.alerta} role="alert">
          {info.message}
        </p>
      )}

      {alternativos.length > 0 && (
        <AlternativosList
          alternativos={alternativos}
          onSelect={elegirAlternativo}
          disabled={pending}
        />
      )}

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="repro-fecha">
          Fecha destino
        </label>
        <input
          className={styles.input}
          id="repro-fecha"
          name="repro-fecha"
          type="date"
          value={fecha}
          onChange={(event) => cambiarFecha(event.target.value)}
        />
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="repro-inicio">
          Horario destino
        </label>
        <select
          className={styles.select}
          id="repro-inicio"
          name="repro-inicio"
          value={inicio}
          aria-required="true"
          aria-invalid={errorInicio !== null}
          aria-describedby={errorInicio === null ? undefined : "repro-inicio-error"}
          onChange={(event) => elegirSlot(event.target.value)}
        >
          {inicio === "" && <option value="">Elegí un horario</option>}
          {opcionActual !== null && (
            <option value={opcionActual}>
              Actual ({formatearHora(ficha.inicio)}–{formatearHora(ficha.fin)})
            </option>
          )}
          {opcionAlternativa !== null && (
            <option value={opcionAlternativa.inicio}>
              {formatearHora(opcionAlternativa.inicio)}–
              {formatearHora(opcionAlternativa.fin)}
            </option>
          )}
          {libres.map((franja) => (
            <option key={franja.inicio} value={franja.inicio}>
              {formatearHora(franja.inicio)}–{formatearHora(franja.fin)}
            </option>
          ))}
        </select>
        {errorInicio !== null && (
          <p className={styles.error} id="repro-inicio-error" role="alert">
            {errorInicio}
          </p>
        )}
        {agenda.estado.status === "loading" && (
          <p className={styles.estado} role="status">
            Cargando horarios…
          </p>
        )}
        {agenda.estado.status === "success" && libres.length === 0 && (
          <p className={styles.estado}>
            No hay horarios libres para esa fecha.
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="repro-duracion">
          Duración
        </label>
        <select
          className={styles.select}
          id="repro-duracion"
          name="repro-duracion"
          value={duracionMin}
          aria-invalid={errorDuracion !== null}
          aria-describedby={
            errorDuracion === null ? undefined : "repro-duracion-error"
          }
          onChange={(event) => setDuracionMin(Number(event.target.value))}
        >
          {opciones.map((opcion) => (
            <option key={opcion} value={opcion}>
              {formatearDuracion(opcion)}
            </option>
          ))}
        </select>
        {errorDuracion !== null && (
          <p className={styles.error} id="repro-duracion-error" role="alert">
            {errorDuracion}
          </p>
        )}
      </div>

      <button
        className={styles.enviar}
        type="submit"
        disabled={pending || inicio === ""}
      >
        {pending ? "Reprogramando…" : "Confirmar reprogramación"}
      </button>
    </form>
  );
}

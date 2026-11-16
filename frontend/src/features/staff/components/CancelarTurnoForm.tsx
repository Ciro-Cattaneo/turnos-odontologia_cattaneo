/**
 * Cancelación staff: normal con `DELETE` sin motivo y forzada `<3 h` con
 * motivo obligatorio antes de enviar (D-8, RN-TU-04). El `422` del backend
 * reabre el campo cuando los relojes difieren.
 */

import { useEffect, useState, type FormEvent } from "react";

import { ApiHttpError } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import { cancelar, type TurnoFichaOut } from "../../../shared/api/staff";
import { esCancelacionForzada } from "../../../shared/config";
import { useExpirarSesion } from "../sesion";
import styles from "./OperacionTurno.module.css";

interface CancelarTurnoFormProps {
  turnoId: string;
  ficha: TurnoFichaOut;
  onCancelado: () => Promise<void>;
  onEstadoTerminal: (mensaje: string) => Promise<void>;
  onCancelar: () => void;
}

export function CancelarTurnoForm({
  turnoId,
  ficha,
  onCancelado,
  onEstadoTerminal,
  onCancelar,
}: CancelarTurnoFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const forzada = esCancelacionForzada(ficha.inicio);
  const [mostrarMotivo, setMostrarMotivo] = useState<boolean>(forzada);
  const [motivoRequerido, setMotivoRequerido] = useState<boolean>(forzada);
  const [motivo, setMotivo] = useState<string>("");
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (info?.codigo === "motivo_requerido") {
      document.getElementById("cancelar-motivo")?.focus();
    }
  }, [info]);

  const confirmarHabilitado =
    !pending && (!motivoRequerido || motivo.trim() !== "");

  const enviar = async (): Promise<void> => {
    setPending(true);
    setInfo(null);
    try {
      const valor = motivo.trim();
      await cancelar(turnoId, valor === "" ? undefined : valor);
      await onCancelado();
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "la cancelación");
      if (error.kind === "validation" && error.codigo === "motivo_requerido") {
        setMostrarMotivo(true);
        setMotivoRequerido(true);
        setInfo(error);
        return;
      }
      if (
        error.kind === "validation" &&
        (error.codigo === "turno_ya_cancelado" ||
          error.codigo === "turno_no_cancelable")
      ) {
        await onEstadoTerminal(error.message);
        return;
      }
      setInfo(error);
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!confirmarHabilitado) {
      return;
    }
    void enviar();
  };

  return (
    <form
      className={styles.formulario}
      aria-label="Cancelar turno"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h3 className={styles.titulo}>Cancelar turno</h3>
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

      {forzada && (
        <p className={styles.estado}>
          Faltan menos de 3 horas para el turno: la cancelación es forzada y
          requiere un motivo.
        </p>
      )}

      {mostrarMotivo && (
        <div className={styles.campo}>
          <label className={styles.label} htmlFor="cancelar-motivo">
            Motivo{motivoRequerido ? " (obligatorio)" : ""}
          </label>
          <input
            className={styles.input}
            id="cancelar-motivo"
            name="cancelar-motivo"
            type="text"
            value={motivo}
            aria-required={motivoRequerido}
            aria-invalid={motivoRequerido && motivo.trim() === ""}
            aria-describedby={
              motivoRequerido && motivo.trim() === ""
                ? "cancelar-motivo-error"
                : undefined
            }
            onChange={(event) => setMotivo(event.target.value)}
          />
          {motivoRequerido && motivo.trim() === "" && (
            <p className={styles.error} id="cancelar-motivo-error" role="alert">
              Ingresá un motivo para cancelar con menos de 3 horas.
            </p>
          )}
        </div>
      )}

      <button
        className={styles.enviar}
        type="submit"
        disabled={!confirmarHabilitado}
      >
        {pending ? "Cancelando…" : "Confirmar cancelación"}
      </button>
    </form>
  );
}

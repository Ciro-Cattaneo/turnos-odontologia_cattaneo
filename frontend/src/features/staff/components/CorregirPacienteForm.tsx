/**
 * Corrección de datos de referencia del paciente (§8.2, RN-PA-02): solo DNI,
 * teléfono y obra social; nombre y email quedan en modo lectura. El `409
 * dni_duplicado` informa sin fusionar y el `400` marca el campo indicado.
 */

import { useEffect, useState, type FormEvent } from "react";

import { ApiHttpError } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import {
  corregirPaciente,
  type PacienteFicha,
} from "../../../shared/api/staff";
import { useExpirarSesion } from "../sesion";
import styles from "./OperacionTurno.module.css";

interface CorregirPacienteFormProps {
  turnoId: string;
  paciente: PacienteFicha;
  onCorregido: () => Promise<void>;
  onCancelar: () => void;
}

const CAMPOS_CORREGIBLES = [
  { campo: "dni", id: "corregir-dni" },
  { campo: "telefono", id: "corregir-telefono" },
  { campo: "obra_social", id: "corregir-obra-social" },
] as const;

export function CorregirPacienteForm({
  turnoId,
  paciente,
  onCorregido,
  onCancelar,
}: CorregirPacienteFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [dni, setDni] = useState<string>(paciente.dni ?? "");
  const [telefono, setTelefono] = useState<string>(paciente.telefono ?? "");
  const [obraSocial, setObraSocial] = useState<string>(
    paciente.obra_social ?? "",
  );
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (info === null) {
      return;
    }
    const primero = CAMPOS_CORREGIBLES.find(
      ({ campo }) => info.fieldErrors[campo] !== undefined,
    );
    if (primero !== undefined) {
      document.getElementById(primero.id)?.focus();
    }
  }, [info]);

  const errorDe = (campo: string): string | undefined =>
    info?.fieldErrors[campo];

  const enviar = async (): Promise<void> => {
    setPending(true);
    setInfo(null);
    try {
      await corregirPaciente(turnoId, {
        dni: dni.trim(),
        telefono: telefono.trim(),
        obra_social: obraSocial.trim(),
      });
      await onCorregido();
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setInfo(mensajeDeError(err, "la corrección de datos"));
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (pending) {
      return;
    }
    void enviar();
  };

  const errorDni = errorDe("dni");
  const errorTelefono = errorDe("telefono");
  const errorObraSocial = errorDe("obra_social");

  return (
    <form
      className={styles.formulario}
      aria-label="Corregir datos del paciente"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h3 className={styles.titulo}>Corregir datos del paciente</h3>
        <button
          type="button"
          className={styles.secundario}
          disabled={pending}
          onClick={onCancelar}
        >
          Volver
        </button>
      </div>

      <p className={styles.estado}>
        Nombre: {paciente.nombre ?? "—"} (no editable)
      </p>
      <p className={styles.estado}>
        Email: {paciente.email ?? "—"} (no editable)
      </p>

      {info !== null && info.kind !== "field" && (
        <p className={styles.alerta} role="alert">
          {info.message}
        </p>
      )}

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="corregir-dni">
          DNI
        </label>
        <input
          className={styles.input}
          id="corregir-dni"
          name="corregir-dni"
          type="text"
          inputMode="numeric"
          value={dni}
          aria-invalid={errorDni !== undefined}
          aria-describedby={errorDni !== undefined ? "corregir-dni-error" : undefined}
          onChange={(event) => setDni(event.target.value)}
        />
        {errorDni !== undefined && (
          <p className={styles.error} id="corregir-dni-error" role="alert">
            {errorDni}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="corregir-telefono">
          Teléfono
        </label>
        <input
          className={styles.input}
          id="corregir-telefono"
          name="corregir-telefono"
          type="tel"
          value={telefono}
          aria-invalid={errorTelefono !== undefined}
          aria-describedby={
            errorTelefono !== undefined ? "corregir-telefono-error" : undefined
          }
          onChange={(event) => setTelefono(event.target.value)}
        />
        {errorTelefono !== undefined && (
          <p className={styles.error} id="corregir-telefono-error" role="alert">
            {errorTelefono}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="corregir-obra-social">
          Obra social
        </label>
        <input
          className={styles.input}
          id="corregir-obra-social"
          name="corregir-obra-social"
          type="text"
          value={obraSocial}
          aria-invalid={errorObraSocial !== undefined}
          aria-describedby={
            errorObraSocial !== undefined
              ? "corregir-obra-social-error"
              : undefined
          }
          onChange={(event) => setObraSocial(event.target.value)}
        />
        {errorObraSocial !== undefined && (
          <p
            className={styles.error}
            id="corregir-obra-social-error"
            role="alert"
          >
            {errorObraSocial}
          </p>
        )}
      </div>

      <button className={styles.enviar} type="submit" disabled={pending}>
        {pending ? "Guardando…" : "Guardar corrección"}
      </button>
    </form>
  );
}

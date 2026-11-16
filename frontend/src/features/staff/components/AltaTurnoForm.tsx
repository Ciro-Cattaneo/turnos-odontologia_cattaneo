/**
 * Alta de turno desde una franja libre con `origen=recepcion`, cinco datos,
 * duración múltiplo de la granularidad y manejo de 409/403/201 (§6.2–§6.4).
 */

import { useMemo, useState, type FormEvent } from "react";

import { ApiHttpError, type Slot } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import {
  crearTurnoRecepcion,
  type CrearTurnoStaffBody,
  type FranjaLibre,
  type TurnoStaffOut,
} from "../../../shared/api/staff";
import { formatearDuracion, formatearHora } from "../../../shared/format";
import { AlternativosList } from "../../reserva/components/AlternativosList";
import { CampoTexto } from "../../reserva/components/CampoTexto";
import {
  FORM_FIELDS,
  FORM_VALUES_VACIOS,
  type FormErrors,
  type FormField,
  type FormValues,
} from "../../reserva/types";
import { validarFormulario } from "../../reserva/validacion";
import { useExpirarSesion } from "../sesion";
import { esDuracionValida, opcionesDuracion } from "../agenda/duracion";
import styles from "./AltaTurnoForm.module.css";

interface AltaTurnoFormProps {
  profesionalId: string;
  profesionalNombre: string;
  franja: FranjaLibre;
  granularidad: number;
  onCreado: (turno: TurnoStaffOut) => void;
  onCancelar: () => void;
  onRefrescarAgenda: () => void;
}

export function AltaTurnoForm({
  profesionalId,
  profesionalNombre,
  franja,
  granularidad,
  onCreado,
  onCancelar,
  onRefrescarAgenda,
}: AltaTurnoFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [slot, setSlot] = useState<Slot>(() => ({
    inicio: franja.inicio,
    fin: franja.fin,
    duracion_min: franja.duracion_min,
  }));
  const [duracionMin, setDuracionMin] = useState<number>(() =>
    esDuracionValida(franja.duracion_min, granularidad)
      ? franja.duracion_min
      : granularidad,
  );
  const [values, setValues] = useState<FormValues>(FORM_VALUES_VACIOS);
  const [localErrors, setLocalErrors] = useState<FormErrors>({});
  const [errorDuracion, setErrorDuracion] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [alternativos, setAlternativos] = useState<Slot[]>([]);

  const opciones = useMemo(() => opcionesDuracion(granularidad), [granularidad]);

  const serverFieldErrors = useMemo<FormErrors>(() => {
    if (info === null || info.kind !== "field") {
      return {};
    }
    const errores: FormErrors = {};
    for (const campo of FORM_FIELDS) {
      const mensaje = info.fieldErrors[campo];
      if (mensaje !== undefined) {
        errores[campo] = mensaje;
      }
    }
    return errores;
  }, [info]);

  const erroresVisibles: FormErrors = submitted
    ? { ...serverFieldErrors, ...localErrors }
    : serverFieldErrors;

  const setValor = (field: FormField, value: string): void => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setLocalErrors((prev) => {
      if (prev[field] === undefined) {
        return prev;
      }
      const next: FormErrors = { ...prev };
      delete next[field];
      return next;
    });
  };

  const elegirAlternativo = (nuevo: Slot): void => {
    setSlot(nuevo);
    setDuracionMin(nuevo.duracion_min);
    setAlternativos([]);
    setInfo(null);
  };

  const enviar = async (): Promise<void> => {
    setPending(true);
    setInfo(null);
    setAlternativos([]);
    const body: CrearTurnoStaffBody = {
      profesional_id: profesionalId,
      inicio: slot.inicio,
      duracion_min: duracionMin,
      origen: "recepcion",
      paciente: {
        nombre: values.nombre.trim(),
        dni: values.dni.trim(),
        telefono: values.telefono.trim(),
        obra_social: values.obra_social.trim(),
        email: values.email.trim(),
      },
    };
    try {
      const turno = await crearTurnoRecepcion(body);
      onCreado(turno);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "el alta del turno");
      setInfo(error);
      setAlternativos(error.alternativos);
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const errores = validarFormulario(values);
    const duracionInvalida = !esDuracionValida(duracionMin, granularidad);
    setLocalErrors(errores);
    setSubmitted(true);
    setErrorDuracion(
      duracionInvalida
        ? `La duración debe ser múltiplo de ${granularidad} min.`
        : null,
    );
    const primerCampo = FORM_FIELDS.find(
      (field) => errores[field] !== undefined,
    );
    if (primerCampo !== undefined) {
      document.getElementById(`alta-${primerCampo}`)?.focus();
      return;
    }
    if (duracionInvalida) {
      document.getElementById("alta-duracion")?.focus();
      return;
    }
    void enviar();
  };

  const conflictoDeSlot =
    info?.kind === "conflict" && info.codigo !== "dni_duplicado";
  const mostrarAlternativos =
    conflictoDeSlot && alternativos.length > 0;
  const ofrecerReconsultar =
    conflictoDeSlot && alternativos.length === 0;

  return (
    <form
      className={styles.formulario}
      aria-label="Alta de turno"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h2 className={styles.titulo}>Alta de turno</h2>
        <button
          type="button"
          className={styles.secundario}
          disabled={pending}
          onClick={onCancelar}
        >
          Cancelar
        </button>
      </div>

      <p className={styles.slotTexto}>
        Horario elegido:{" "}
        <strong>
          {formatearHora(slot.inicio)}–{formatearHora(slot.fin)}
        </strong>{" "}
        · Profesional: {profesionalNombre}
      </p>

      {info !== null && (
        <p className={styles.alerta} role="alert">
          {info.message}
        </p>
      )}

      {mostrarAlternativos && (
        <AlternativosList
          alternativos={alternativos}
          onSelect={elegirAlternativo}
          disabled={pending}
        />
      )}

      {ofrecerReconsultar && (
        <button
          type="button"
          className={styles.secundario}
          onClick={onRefrescarAgenda}
        >
          Reconsultar agenda
        </button>
      )}

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="alta-duracion">
          Duración
        </label>
        <select
          className={styles.select}
          id="alta-duracion"
          name="alta-duracion"
          value={duracionMin}
          aria-invalid={errorDuracion !== null}
          aria-describedby={
            errorDuracion === null ? undefined : "alta-duracion-error"
          }
          onChange={(event) => {
            setDuracionMin(Number(event.target.value));
            setErrorDuracion(null);
          }}
        >
          {opciones.map((opcion) => (
            <option key={opcion} value={opcion}>
              {formatearDuracion(opcion)}
            </option>
          ))}
        </select>
        {errorDuracion !== null && (
          <p className={styles.error} id="alta-duracion-error" role="alert">
            {errorDuracion}
          </p>
        )}
      </div>

      <fieldset className={styles.grupo}>
        <legend className={styles.leyenda}>Datos del paciente</legend>
        <CampoTexto
          id="alta-nombre"
          label="Nombre y apellido"
          value={values.nombre}
          autoComplete="name"
          error={erroresVisibles.nombre}
          onChange={(value) => setValor("nombre", value)}
        />
        <CampoTexto
          id="alta-dni"
          label="DNI"
          value={values.dni}
          inputMode="numeric"
          autoComplete="off"
          error={erroresVisibles.dni}
          onChange={(value) => setValor("dni", value)}
        />
        <CampoTexto
          id="alta-telefono"
          label="Teléfono"
          type="tel"
          value={values.telefono}
          inputMode="tel"
          autoComplete="tel"
          error={erroresVisibles.telefono}
          onChange={(value) => setValor("telefono", value)}
        />
        <CampoTexto
          id="alta-obra-social"
          label="Obra social"
          value={values.obra_social}
          autoComplete="off"
          error={erroresVisibles.obra_social}
          onChange={(value) => setValor("obra_social", value)}
        />
        <CampoTexto
          id="alta-email"
          label="Email"
          type="email"
          value={values.email}
          inputMode="email"
          autoComplete="email"
          error={erroresVisibles.email}
          onChange={(value) => setValor("email", value)}
        />
      </fieldset>

      <button className={styles.enviar} type="submit" disabled={pending}>
        {pending ? "Creando…" : "Confirmar alta"}
      </button>
    </form>
  );
}

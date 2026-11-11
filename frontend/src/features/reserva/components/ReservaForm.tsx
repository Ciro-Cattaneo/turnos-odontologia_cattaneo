/** Formulario de reserva con validación local y mapeo del 400 por campo (R4). */

import { useMemo, useState, type FormEvent } from "react";

import type { ApiErrorDetail, Slot } from "../../../shared/api/client";
import { formatearDuracion, formatearHora } from "../format";
import {
  FORM_FIELDS,
  FORM_VALUES_VACIOS,
  type FormErrors,
  type FormField,
  type FormValues,
} from "../types";
import { mapearDetalle400, validarFormulario } from "../validacion";
import { CampoTexto } from "./CampoTexto";
import styles from "./ReservaForm.module.css";

interface ReservaFormProps {
  slot: Slot;
  submitting: boolean;
  serverDetail?: ApiErrorDetail | null;
  initialValues?: FormValues;
  onSubmit: (values: FormValues) => void;
}

export function ReservaForm({
  slot,
  submitting,
  serverDetail = null,
  initialValues = FORM_VALUES_VACIOS,
  onSubmit,
}: ReservaFormProps): JSX.Element {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [localErrors, setLocalErrors] = useState<FormErrors>({});
  const [submitted, setSubmitted] = useState(false);

  const detalle = useMemo(() => mapearDetalle400(serverDetail), [serverDetail]);
  const erroresVisibles: FormErrors = submitted
    ? { ...detalle.fieldErrors, ...localErrors }
    : detalle.fieldErrors;

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

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const errores = validarFormulario(values);
    setLocalErrors(errores);
    setSubmitted(true);
    const primerCampo = FORM_FIELDS.find(
      (field) => errores[field] !== undefined,
    );
    if (primerCampo !== undefined) {
      document.getElementById(primerCampo)?.focus();
      return;
    }
    onSubmit({
      nombre: values.nombre.trim(),
      dni: values.dni.trim(),
      telefono: values.telefono.trim(),
      obra_social: values.obra_social.trim(),
      email: values.email.trim(),
    });
  };

  return (
    <form
      className={styles.formulario}
      aria-label="Formulario de reserva"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.slotElegido}>
        <p className={styles.slotTexto}>
          Horario elegido:{" "}
          <strong>
            {formatearHora(slot.inicio)}–{formatearHora(slot.fin)} (
            {formatearDuracion(slot.duracion_min)})
          </strong>
        </p>
      </div>

      {detalle.slotError !== null && (
        <p className={styles.alertaSlot} role="alert">
          {detalle.slotError}
        </p>
      )}
      {detalle.otroError !== null && (
        <p className={styles.alertaSlot} role="alert">
          {detalle.otroError}
        </p>
      )}

      <fieldset className={styles.grupo}>
        <legend className={styles.leyenda}>Datos del paciente</legend>
        <CampoTexto
          id="nombre"
          label="Nombre y apellido"
          value={values.nombre}
          autoComplete="name"
          error={erroresVisibles.nombre}
          onChange={(value) => setValor("nombre", value)}
        />
        <CampoTexto
          id="dni"
          label="DNI"
          value={values.dni}
          inputMode="numeric"
          autoComplete="off"
          error={erroresVisibles.dni}
          onChange={(value) => setValor("dni", value)}
        />
        <CampoTexto
          id="telefono"
          label="Teléfono"
          type="tel"
          value={values.telefono}
          inputMode="tel"
          autoComplete="tel"
          error={erroresVisibles.telefono}
          onChange={(value) => setValor("telefono", value)}
        />
        <CampoTexto
          id="obra_social"
          label="Obra social"
          value={values.obra_social}
          autoComplete="off"
          error={erroresVisibles.obra_social}
          onChange={(value) => setValor("obra_social", value)}
        />
        <CampoTexto
          id="email"
          label="Email"
          type="email"
          value={values.email}
          inputMode="email"
          autoComplete="email"
          error={erroresVisibles.email}
          onChange={(value) => setValor("email", value)}
        />
      </fieldset>

      <button className={styles.enviar} type="submit" disabled={submitting}>
        {submitting ? "Reservando…" : "Confirmar reserva"}
      </button>
    </form>
  );
}

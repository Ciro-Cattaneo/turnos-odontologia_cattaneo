/** Selector de profesional activo; lista vacía no ofrece fecha ni formulario (R2). */

import type { Profesional } from "../../../shared/api/reserva";
import styles from "./ProfesionalSelector.module.css";

interface ProfesionalSelectorProps {
  profesionales: Profesional[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export function ProfesionalSelector({
  profesionales,
  value,
  onChange,
  disabled = false,
}: ProfesionalSelectorProps): JSX.Element {
  if (profesionales.length === 0) {
    return (
      <p className={styles.vacio} role="status">
        No hay profesionales disponibles en este momento. Volvé a intentarlo más
        tarde.
      </p>
    );
  }
  return (
    <div className={styles.campo}>
      <label className={styles.label} htmlFor="profesional">
        Profesional
      </label>
      <select
        className={styles.select}
        id="profesional"
        name="profesional"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Elegí un profesional</option>
        {profesionales.map((profesional) => (
          <option key={profesional.id} value={profesional.id}>
            {profesional.nombre}
            {profesional.especialidad !== null
              ? ` — ${profesional.especialidad}`
              : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

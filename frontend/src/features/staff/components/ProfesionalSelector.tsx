/** Selector de profesional activo de la agenda staff (D-5, §5.2). */

import type { Profesional } from "../../../shared/api/reserva";
import styles from "./Agenda.module.css";

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
        No hay profesionales disponibles en este momento.
      </p>
    );
  }
  return (
    <div className={styles.selector}>
      <label className={styles.label} htmlFor="staff-profesional">
        Profesional
      </label>
      <select
        className={styles.select}
        id="staff-profesional"
        name="profesional"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
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

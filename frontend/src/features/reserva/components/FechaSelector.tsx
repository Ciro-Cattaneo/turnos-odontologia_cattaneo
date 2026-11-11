/** Selector de fecha de búsqueda (R2, D-5). */

import styles from "./FechaSelector.module.css";

interface FechaSelectorProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function FechaSelector({
  value,
  onChange,
  disabled = false,
}: FechaSelectorProps): JSX.Element {
  return (
    <div className={styles.campo}>
      <label className={styles.label} htmlFor="fecha">
        Fecha
      </label>
      <input
        className={styles.input}
        id="fecha"
        name="fecha"
        type="date"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

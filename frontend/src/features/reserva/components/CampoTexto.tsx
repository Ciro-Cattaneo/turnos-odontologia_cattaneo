/** Campo de texto etiquetado con error anunciado (R13, D-7). */

import styles from "./CampoTexto.module.css";

interface CampoTextoProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: "text" | "email" | "tel" | "password";
  autoComplete?: string;
  inputMode?: "text" | "numeric" | "tel" | "email";
}

export function CampoTexto({
  id,
  label,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
  inputMode,
}: CampoTextoProps): JSX.Element {
  const errorId = `${id}-error`;
  const tieneError = error !== undefined;
  return (
    <div className={styles.campo}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <input
        className={styles.input}
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        inputMode={inputMode}
        aria-required="true"
        aria-invalid={tieneError}
        aria-describedby={tieneError ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error !== undefined && (
        <p className={styles.error} id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

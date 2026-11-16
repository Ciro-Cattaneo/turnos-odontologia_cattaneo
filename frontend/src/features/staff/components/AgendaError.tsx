/** Error accionable de la agenda: 404 recarga profesionales, 403 sin datos (D-13). */

import type { StaffErrorInfo } from "../../../shared/api/errores";
import styles from "./Agenda.module.css";

interface AgendaErrorProps {
  info: StaffErrorInfo;
  onReintentar: () => void;
  onRecargarProfesionales: () => void;
}

export function AgendaError({
  info,
  onReintentar,
  onRecargarProfesionales,
}: AgendaErrorProps): JSX.Element {
  const noEncontrado = info.kind === "not_found";
  const prohibido = info.kind === "forbidden";

  return (
    <div className={styles.error} role="alert">
      <p>
        {noEncontrado ? "El profesional no está disponible." : info.message}
      </p>
      {noEncontrado && (
        <button
          type="button"
          className={styles.boton}
          onClick={onRecargarProfesionales}
        >
          Recargar profesionales
        </button>
      )}
      {!noEncontrado && !prohibido && (
        <button type="button" className={styles.boton} onClick={onReintentar}>
          Reintentar
        </button>
      )}
    </div>
  );
}

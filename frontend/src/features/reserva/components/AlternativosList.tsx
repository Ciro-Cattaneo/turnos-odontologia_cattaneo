/** Alternativos del mismo día ante un 409 (R6). */

import type { Slot } from "../../../shared/api/client";
import { formatearHora } from "../format";
import styles from "./AlternativosList.module.css";

interface AlternativosListProps {
  alternativos: Slot[];
  onSelect: (slot: Slot) => void;
  disabled?: boolean;
}

export function AlternativosList({
  alternativos,
  onSelect,
  disabled = false,
}: AlternativosListProps): JSX.Element {
  if (alternativos.length === 0) {
    return (
      <p className={styles.vacio} role="status">
        Ese horario se ocupó y no hay alternativos para ese día. Probá con otra
        fecha.
      </p>
    );
  }
  return (
    <section className={styles.contenedor} aria-label="Horarios alternativos">
      <p className={styles.mensaje} role="alert">
        Ese horario se ocupó. Elegí otro horario para el mismo día:
      </p>
      <ul className={styles.lista}>
        {alternativos.map((slot) => {
          const inicio = formatearHora(slot.inicio);
          const fin = formatearHora(slot.fin);
          return (
            <li key={slot.inicio}>
              <button
                type="button"
                className={styles.opcion}
                disabled={disabled}
                aria-label={`${inicio} a ${fin}`}
                onClick={() => onSelect(slot)}
              >
                {inicio}–{fin}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

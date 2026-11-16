/** Lista de slots libres tal como los devuelve el contrato (R3, D-5). */

import type { Slot } from "../../../shared/api/client";
import { formatearDuracion, formatearHora } from "../../../shared/format";
import styles from "./SlotList.module.css";

interface SlotListProps {
  slots: Slot[];
  onSelect: (slot: Slot) => void;
  disabled?: boolean;
  seleccionado?: string | null;
}

export function SlotList({
  slots,
  onSelect,
  disabled = false,
  seleccionado = null,
}: SlotListProps): JSX.Element | null {
  if (slots.length === 0) {
    return null;
  }
  return (
    <ul className={styles.lista} aria-label="Horarios disponibles">
      {slots.map((slot) => {
        const inicio = formatearHora(slot.inicio);
        const fin = formatearHora(slot.fin);
        const duracion = formatearDuracion(slot.duracion_min);
        return (
          <li key={slot.inicio}>
            <button
              type="button"
              className={styles.opcion}
              disabled={disabled}
              aria-pressed={seleccionado === slot.inicio}
              aria-label={`${inicio} a ${fin}, ${duracion}`}
              onClick={() => onSelect(slot)}
            >
              <span className={styles.horario}>
                {inicio}–{fin}
              </span>
              <span className={styles.duracion}>{duracion}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

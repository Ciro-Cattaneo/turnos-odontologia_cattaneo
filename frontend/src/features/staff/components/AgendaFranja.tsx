/** Franja operativa de la agenda staff: libre, ocupado o bloqueado (D-15). */

import type {
  FranjaBloqueado,
  FranjaCerrado,
  FranjaLibre,
  FranjaOcupado,
  FranjaStaff,
} from "../../../shared/api/staff";
import {
  formatearDuracion,
  formatearHora,
} from "../../../shared/format";
import styles from "./Agenda.module.css";

export type FranjaOperativa = Exclude<FranjaStaff, FranjaCerrado>;

interface AgendaFranjaProps {
  franja: FranjaLibre | FranjaOcupado | FranjaBloqueado;
  puedeCrear: boolean;
  onAbrirTurno: (turnoId: string) => void;
  onCrearTurno: (franja: FranjaLibre) => void;
}

export function AgendaFranja({
  franja,
  puedeCrear,
  onAbrirTurno,
  onCrearTurno,
}: AgendaFranjaProps): JSX.Element {
  const horario = `${formatearHora(franja.inicio)}–${formatearHora(franja.fin)}`;
  if (franja.tipo === "libre") {
    return (
      <li className={`${styles.franja} ${styles.libre}`}>
        <span className={styles.tipo}>Libre</span>
        <span className={styles.horario}>{horario}</span>
        <span className={styles.duracion}>
          {formatearDuracion(franja.duracion_min)}
        </span>
        {puedeCrear && (
          <button
            type="button"
            className={styles.accion}
            aria-label={`Crear turno de las ${formatearHora(franja.inicio)}`}
            onClick={() => onCrearTurno(franja)}
          >
            Crear turno
          </button>
        )}
      </li>
    );
  }
  if (franja.tipo === "ocupado") {
    return (
      <li className={`${styles.franja} ${styles.ocupado}`}>
        <span className={styles.tipo}>Ocupado</span>
        <span className={styles.estadoFranja}>{franja.estado}</span>
        <span className={styles.paciente}>{franja.paciente.nombre}</span>
        <span className={styles.horario}>{horario}</span>
        <button
          type="button"
          className={styles.accion}
          aria-label={`Ver detalle del turno de las ${formatearHora(franja.inicio)}`}
          onClick={() => onAbrirTurno(franja.turno_id)}
        >
          Ver detalle
        </button>
      </li>
    );
  }
  return (
    <li className={`${styles.franja} ${styles.bloqueado}`}>
      <span className={styles.tipo}>Bloqueado</span>
      <span className={styles.motivo}>{franja.motivo}</span>
      <span className={styles.horario}>{horario}</span>
    </li>
  );
}

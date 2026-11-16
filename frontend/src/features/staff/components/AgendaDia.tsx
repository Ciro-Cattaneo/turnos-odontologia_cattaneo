/** Un día de la agenda staff: franjas operativas y cerrados del día (§5.3). */

import type {
  AgendaDia as DiaAgenda,
  FranjaCerrado,
  FranjaLibre,
} from "../../../shared/api/staff";
import {
  formatearFechaCalendario,
  formatearHora,
} from "../../../shared/format";
import { AgendaFranja, type FranjaOperativa } from "./AgendaFranja";
import styles from "./Agenda.module.css";

interface AgendaDiaProps {
  dia: DiaAgenda;
  puedeCrear: boolean;
  onAbrirTurno: (turnoId: string) => void;
  onCrearTurno: (franja: FranjaLibre) => void;
}

export function AgendaDia({
  dia,
  puedeCrear,
  onAbrirTurno,
  onCrearTurno,
}: AgendaDiaProps): JSX.Element {
  const operativas: FranjaOperativa[] = [];
  const cerrados: FranjaCerrado[] = [];
  for (const franja of dia.franjas) {
    if (franja.tipo === "cerrado") {
      cerrados.push(franja);
    } else {
      operativas.push(franja);
    }
  }
  const etiqueta = formatearFechaCalendario(dia.fecha);

  return (
    <section className={styles.dia} aria-label={`Agenda del ${etiqueta}`}>
      <h2 className={styles.fechaDia}>{etiqueta}</h2>

      {operativas.length > 0 && (
        <ul className={styles.franjas} aria-label={`Franjas del ${etiqueta}`}>
          {operativas.map((franja) => (
            <AgendaFranja
              key={`${franja.tipo}-${franja.inicio}`}
              franja={franja}
              puedeCrear={puedeCrear}
              onAbrirTurno={onAbrirTurno}
              onCrearTurno={onCrearTurno}
            />
          ))}
        </ul>
      )}

      {cerrados.length > 0 && (
        <section className={styles.cerrados}>
          <h3 className={styles.subtitulo}>Turnos cerrados del día</h3>
          <ul className={styles.listaCerrados}>
            {cerrados.map((franja) => (
              <li key={franja.turno_id} className={styles.itemCerrado}>
                <span className={styles.estadoCerrado}>{franja.estado}</span>
                <span className={styles.paciente}>{franja.paciente.nombre}</span>
                <span className={styles.horario}>
                  {formatearHora(franja.inicio)}–{formatearHora(franja.fin)}
                </span>
                <button
                  type="button"
                  className={styles.accion}
                  aria-label={`Ver detalle del turno de las ${formatearHora(franja.inicio)}`}
                  onClick={() => onAbrirTurno(franja.turno_id)}
                >
                  Ver detalle
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {operativas.length === 0 && cerrados.length === 0 && (
        <p className={styles.vacio}>
          No hay horarios ni turnos para este período.
        </p>
      )}
    </section>
  );
}

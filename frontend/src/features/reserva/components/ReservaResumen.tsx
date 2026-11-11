/** Resumen del 201 y link de cancelación (R5, D-6). */

import type { TurnoOut } from "../../../shared/api/reserva";
import { formatearDuracion, formatearFecha, formatearHora } from "../format";
import styles from "./ReservaResumen.module.css";

interface ReservaResumenProps {
  turno: TurnoOut;
}

export function ReservaResumen({ turno }: ReservaResumenProps): JSX.Element {
  return (
    <section className={styles.resumen} aria-label="Resumen de la reserva">
      <h2 className={styles.titulo}>Reserva confirmada</h2>
      <dl className={styles.datos}>
        <dt>Profesional</dt>
        <dd>{turno.profesional.nombre}</dd>
        <dt>Fecha</dt>
        <dd>{formatearFecha(turno.inicio)}</dd>
        <dt>Hora</dt>
        <dd>
          {formatearHora(turno.inicio)}–{formatearHora(turno.fin)}
        </dd>
        <dt>Duración</dt>
        <dd>{formatearDuracion(turno.duracion_min)}</dd>
        <dt>Estado</dt>
        <dd>{turno.estado}</dd>
      </dl>

      {turno.notificaciones_encoladas ? (
        <p className={styles.avisoInfo}>
          La confirmación y los recordatorios se enviarán por mail.
        </p>
      ) : (
        <p className={styles.avisoAlerta} role="alert">
          El turno quedó reservado, pero no se pudieron encolar los mails.
          Contactá al consultorio para coordinar la confirmación.
        </p>
      )}

      <a className={styles.cancelar} href={turno.cancel_url}>
        Cancelar turno
      </a>
    </section>
  );
}

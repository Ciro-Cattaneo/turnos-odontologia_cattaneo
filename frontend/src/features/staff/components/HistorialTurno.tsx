/**
 * Historial auditable paginado por cursor (§8.1, D-11): acción, actor, fecha y
 * cambios leídos de forma defensiva; "Ver más" agrega la página siguiente.
 */

import type { AuditoriaItem } from "../../../shared/api/staff";
import { formatearFechaHora } from "../../../shared/format";
import { actorDeDetalle, cambiosDeDetalle } from "../agenda/historial";
import styles from "./TurnoDetalle.module.css";

interface HistorialTurnoProps {
  items: AuditoriaItem[];
  nextCursor: string | null;
  cargando: boolean;
  error: string | null;
  onVerMas: () => void;
}

export function HistorialTurno({
  items,
  nextCursor,
  cargando,
  error,
  onVerMas,
}: HistorialTurnoProps): JSX.Element {
  return (
    <section className={styles.historial} aria-label="Historial del turno">
      <h3 className={styles.subtitulo}>Historial</h3>

      {error !== null && (
        <p className={styles.alerta} role="alert">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <p className={styles.estado}>Sin movimientos registrados.</p>
      ) : (
        <ul className={styles.listaHistorial}>
          {items.map((item) => {
            const cambios = cambiosDeDetalle(item.detalle);
            return (
              <li key={item.id} className={styles.itemHistorial}>
                <p className={styles.accionHistorial}>
                  <strong>{item.accion}</strong> ·{" "}
                  {actorDeDetalle(item.actor)} ·{" "}
                  <time dateTime={item.created_at}>
                    {formatearFechaHora(item.created_at)}
                  </time>
                </p>
                {cambios.length > 0 && (
                  <ul className={styles.cambios}>
                    {cambios.map((cambio) => (
                      <li key={`${item.id}-${cambio.campo}`}>
                        {cambio.etiqueta}: {cambio.antes} → {cambio.despues}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {nextCursor !== null && (
        <button
          type="button"
          className={styles.accion}
          disabled={cargando}
          onClick={onVerMas}
        >
          {cargando ? "Cargando historial…" : "Ver más historial"}
        </button>
      )}
    </section>
  );
}

/**
 * Tabla del reporte y panel de totales (D-5/D-6): `null` → "—", `>100` visible
 * sin recorte, scroll interno en 360px y `zona` siempre visible.
 */

import type { ReporteOcupacion } from "../../../../shared/api/admin";
import { formatearPorcentaje } from "../porcentaje";
import styles from "./Reporte.module.css";

interface ReporteTablaProps {
  reporte: ReporteOcupacion;
}

export function ReporteTabla({ reporte }: ReporteTablaProps): JSX.Element {
  const hayExcedidos = reporte.items.some(
    (fila) =>
      fila.porcentaje_ocupacion !== null && fila.porcentaje_ocupacion > 100,
  );

  return (
    <>
      <p className={styles.zona}>Zona: {reporte.zona}</p>

      {reporte.items.length === 0 ? (
        <p className={styles.vacio}>
          No hay turnos para el rango y el profesional elegido.
        </p>
      ) : (
        <div className={styles.tablaScroll}>
          <table className={styles.tabla}>
            <caption className={styles.caption}>
              Ocupación por profesional
            </caption>
            <thead>
              <tr>
                <th scope="col">Profesional</th>
                <th scope="col">Turnos</th>
                <th scope="col">Atendidos</th>
                <th scope="col">Ausentes</th>
                <th scope="col">Cancelados</th>
                <th scope="col">Pendientes</th>
                <th scope="col">Min. disponibles</th>
                <th scope="col">Min. ocupados</th>
                <th scope="col">%</th>
              </tr>
            </thead>
            <tbody>
              {reporte.items.map((fila) => (
                <tr key={fila.profesional.id}>
                  <th scope="row">{fila.profesional.nombre}</th>
                  <td>{fila.turnos}</td>
                  <td>{fila.atendidos}</td>
                  <td>{fila.ausentes}</td>
                  <td>{fila.cancelados}</td>
                  <td>{fila.pendientes}</td>
                  <td>{fila.minutos_disponibles}</td>
                  <td>{fila.minutos_ocupados}</td>
                  <td
                    className={
                      fila.porcentaje_ocupacion !== null &&
                      fila.porcentaje_ocupacion > 100
                        ? styles.excedido
                        : undefined
                    }
                    aria-label={
                      fila.porcentaje_ocupacion === null
                        ? "Sin capacidad registrada"
                        : undefined
                    }
                  >
                    {formatearPorcentaje(fila.porcentaje_ocupacion)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hayExcedidos && (
        <p className={styles.avisoExcedido} role="status">
          Hay filas con ocupación mayor al 100 % (sobreasignación).
        </p>
      )}

      <section
        className={styles.totales}
        aria-label="Totales del reporte"
      >
        <h2 className={styles.tituloTotales}>Totales</h2>
        <ul className={styles.listaTotales}>
          <li>Turnos: {reporte.totales.turnos}</li>
          <li>Atendidos: {reporte.totales.atendidos}</li>
          <li>Ausentes: {reporte.totales.ausentes}</li>
          <li>Cancelados: {reporte.totales.cancelados}</li>
          <li>Pendientes: {reporte.totales.pendientes}</li>
          <li>Minutos disponibles: {reporte.totales.minutos_disponibles}</li>
          <li>Minutos ocupados: {reporte.totales.minutos_ocupados}</li>
          <li>
            Porcentaje: {formatearPorcentaje(reporte.totales.porcentaje_ocupacion)}
          </li>
        </ul>
      </section>
    </>
  );
}

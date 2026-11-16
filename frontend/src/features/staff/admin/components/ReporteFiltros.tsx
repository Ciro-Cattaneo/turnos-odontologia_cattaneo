/**
 * Filtros del reporte (D-3/D-6): rango explícito con validación local y
 * profesional opcional. El submit nunca emite GET si el rango es inválido.
 */

import type { FormEvent } from "react";

import type { ProfesionalAdmin } from "../../../../shared/api/admin";
import type { ErroresRango } from "../rango";
import styles from "./Reporte.module.css";

interface ReporteFiltrosProps {
  desde: string;
  hasta: string;
  profesionalId: string;
  profesionales: ProfesionalAdmin[];
  errores: ErroresRango;
  enviando: boolean;
  onDesde: (valor: string) => void;
  onHasta: (valor: string) => void;
  onProfesional: (valor: string) => void;
  onConsultar: () => void;
}

export function ReporteFiltros({
  desde,
  hasta,
  profesionalId,
  profesionales,
  errores,
  enviando,
  onDesde,
  onHasta,
  onProfesional,
  onConsultar,
}: ReporteFiltrosProps): JSX.Element {
  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onConsultar();
  };

  return (
    <form
      className={styles.filtros}
      aria-label="Filtros del reporte"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.campo}>
        <label className={styles.label} htmlFor="reporte-desde">
          Desde
        </label>
        <input
          className={styles.input}
          id="reporte-desde"
          name="desde"
          type="date"
          value={desde}
          aria-required="true"
          aria-invalid={errores.desde !== undefined}
          aria-describedby={
            errores.desde === undefined ? undefined : "reporte-desde-error"
          }
          onChange={(event) => onDesde(event.target.value)}
        />
        {errores.desde !== undefined && (
          <p className={styles.error} id="reporte-desde-error" role="alert">
            {errores.desde}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="reporte-hasta">
          Hasta
        </label>
        <input
          className={styles.input}
          id="reporte-hasta"
          name="hasta"
          type="date"
          value={hasta}
          aria-required="true"
          aria-invalid={errores.hasta !== undefined}
          aria-describedby={
            errores.hasta === undefined ? undefined : "reporte-hasta-error"
          }
          onChange={(event) => onHasta(event.target.value)}
        />
        {errores.hasta !== undefined && (
          <p className={styles.error} id="reporte-hasta-error" role="alert">
            {errores.hasta}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor="reporte-profesional">
          Profesional
        </label>
        <select
          className={styles.select}
          id="reporte-profesional"
          name="profesional_id"
          value={profesionalId}
          onChange={(event) => onProfesional(event.target.value)}
        >
          <option value="">Todos</option>
          {profesionales.map((profesional) => (
            <option key={profesional.id} value={profesional.id}>
              {profesional.nombre}
            </option>
          ))}
        </select>
      </div>

      <button className={styles.consultar} type="submit" disabled={enviando}>
        {enviando ? "Consultando." : "Consultar"}
      </button>
    </form>
  );
}

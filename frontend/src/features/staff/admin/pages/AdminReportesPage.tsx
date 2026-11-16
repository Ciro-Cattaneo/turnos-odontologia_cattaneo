/**
 * Reporte de ocupación (D-1/D-5/D-6/D-10): rango con validación local ≤366,
 * filtro opcional, filas por profesional, totales, zona y aviso fijo de v1 sin
 * exportación. Gating por rol y estados carga/error/403.
 */

import { useEffect, useState } from "react";

import type { StaffErrorInfo } from "../../../../shared/api/errores";
import { ReporteFiltros } from "../components/ReporteFiltros";
import { ReporteTabla } from "../components/ReporteTabla";
import { SinPermisoAdmin } from "../components/SinPermisoAdmin";
import { useReporteOcupacion } from "../hooks/useReporteOcupacion";
import {
  validarRango,
  type ErroresRango,
} from "../rango";
import { useSesionAdmin } from "../useSesionAdmin";
import styles from "./AdminReportesPage.module.css";

function erroresDeCampos(error: StaffErrorInfo | null): ErroresRango {
  if (error === null || error.kind !== "field") {
    return {};
  }
  const errores: ErroresRango = {};
  if (error.fieldErrors["desde"] !== undefined) {
    errores.desde = error.fieldErrors["desde"];
  }
  if (error.fieldErrors["hasta"] !== undefined) {
    errores.hasta = error.fieldErrors["hasta"];
  }
  return errores;
}

export function AdminReportesPage(): JSX.Element {
  const { esAdmin } = useSesionAdmin();

  if (!esAdmin) {
    return <SinPermisoAdmin />;
  }

  return <ReporteContenido />;
}

function ReporteContenido(): JSX.Element {
  const {
    estado,
    reporte,
    profesionales,
    error,
    desde,
    hasta,
    profesionalId,
    cambiarDesde,
    cambiarHasta,
    cambiarProfesional,
    consultar,
    reintentar,
  } = useReporteOcupacion();

  const [errores, setErrores] = useState<ErroresRango>({});

  const erroresServidor = erroresDeCampos(error);
  const errorDesde = errores.desde ?? erroresServidor.desde;
  const errorHasta = errores.hasta ?? erroresServidor.hasta;

  useEffect(() => {
    if (errorHasta !== undefined) {
      document.getElementById("reporte-hasta")?.focus();
    } else if (errorDesde !== undefined) {
      document.getElementById("reporte-desde")?.focus();
    }
  }, [errorHasta, errorDesde]);

  const enviar = (): void => {
    const nuevos = validarRango(desde, hasta);
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) {
      return;
    }
    void consultar();
  };

  const cambiarDesdeLocal = (valor: string): void => {
    setErrores((previos) => ({ ...previos, desde: undefined }));
    cambiarDesde(valor);
  };

  const cambiarHastaLocal = (valor: string): void => {
    setErrores((previos) => ({ ...previos, hasta: undefined }));
    cambiarHasta(valor);
  };

  const errorGeneral =
    error !== null && error.kind !== "field" ? error : null;

  return (
    <section className={styles.pagina} aria-labelledby="titulo-reportes">
      <h1 className={styles.titulo} id="titulo-reportes">
        Reportes
      </h1>

      <p className={styles.avisoV1}>
        En v1 el reporte es solo tabla: no hay exportación a CSV ni Excel.
      </p>

      <ReporteFiltros
        desde={desde}
        hasta={hasta}
        profesionalId={profesionalId}
        profesionales={profesionales}
        errores={{ desde: errorDesde, hasta: errorHasta }}
        enviando={estado === "cargando"}
        onDesde={cambiarDesdeLocal}
        onHasta={cambiarHastaLocal}
        onProfesional={cambiarProfesional}
        onConsultar={enviar}
      />

      {estado === "cargando" && (
        <p className={styles.estado} role="status">
          Cargando reporte de ocupación.
        </p>
      )}

      {estado === "error" && errorGeneral !== null && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{errorGeneral.message}</p>
          {errorGeneral.kind !== "forbidden" && (
            <button
              type="button"
              className={styles.secundario}
              onClick={() => {
                void reintentar();
              }}
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {estado === "listo" && reporte !== null && (
        <ReporteTabla reporte={reporte} />
      )}
    </section>
  );
}

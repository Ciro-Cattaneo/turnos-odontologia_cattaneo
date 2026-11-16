/**
 * Panel staff de notificaciones fallidas (§9, D-12): primera página con
 * `limit=20`, "Cargar más" por cursor opaco y deduplicación por `id`; solo
 * recepción/admin, con estado vacío y errores traducidos (D-13).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiHttpError } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import { getFallidas, type FallidaItem } from "../../../shared/api/staff";
import { formatearFechaHora, formatearHora } from "../../../shared/format";
import { useExpirarSesion, useStaffSesion } from "../sesion";
import styles from "./NotificacionesPage.module.css";

type EstadoPanel = "loading" | "success" | "error";

function deduplicar(items: FallidaItem[]): FallidaItem[] {
  const vistos = new Set<string>();
  const unicos: FallidaItem[] = [];
  for (const item of items) {
    if (vistos.has(item.id)) {
      continue;
    }
    vistos.add(item.id);
    unicos.push(item);
  }
  return unicos;
}

export function NotificacionesPage(): JSX.Element {
  const sesion = useStaffSesion();
  const expirarSesion = useExpirarSesion();
  const esOdontologo = sesion.rol === "odontologo";

  const [items, setItems] = useState<FallidaItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [estado, setEstado] = useState<EstadoPanel>("loading");
  const [cargandoMas, setCargandoMas] = useState(false);
  const [error, setError] = useState<StaffErrorInfo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargarPrimera = useCallback(async (): Promise<void> => {
    setEstado("loading");
    setError(null);
    setAviso(null);
    try {
      const page = await getFallidas();
      setItems(deduplicar(page.items));
      setCursor(page.next_cursor);
      setEstado("success");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setError(mensajeDeError(err, "el panel de notificaciones"));
      setEstado("error");
    }
  }, [expirarSesion]);

  useEffect(() => {
    if (esOdontologo) {
      setEstado("success");
      return;
    }
    void cargarPrimera();
  }, [esOdontologo, cargarPrimera]);

  const cargarMas = async (): Promise<void> => {
    if (cursor === null || cargandoMas) {
      return;
    }
    setCargandoMas(true);
    setError(null);
    setAviso(null);
    try {
      const page = await getFallidas(cursor);
      setItems((previos) => deduplicar([...previos, ...page.items]));
      setCursor(page.next_cursor);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      if (err instanceof ApiHttpError && err.status === 400) {
        setAviso(
          "El listado se reinició porque el cursor dejó de ser válido.",
        );
        try {
          const page = await getFallidas();
          setItems(deduplicar(page.items));
          setCursor(page.next_cursor);
        } catch (reinicio: unknown) {
          if (reinicio instanceof ApiHttpError && reinicio.status === 401) {
            expirarSesion();
            return;
          }
          setError(mensajeDeError(reinicio, "el panel de notificaciones"));
        }
        return;
      }
      setError(mensajeDeError(err, "el panel de notificaciones"));
    } finally {
      setCargandoMas(false);
    }
  };

  return (
    <section className={styles.pagina} aria-labelledby="titulo-notificaciones">
      <h1 className={styles.titulo} id="titulo-notificaciones">
        Notificaciones fallidas
      </h1>

      {esOdontologo && (
        <p className={styles.alerta} role="alert">
          No tenés permiso para esta acción.
        </p>
      )}

      {!esOdontologo && estado === "loading" && (
        <p className={styles.estado} role="status">
          Cargando notificaciones fallidas…
        </p>
      )}

      {!esOdontologo && estado === "error" && error !== null && (
        <div className={styles.alerta} role="alert">
          <p>{error.message}</p>
          {error.kind !== "forbidden" && (
            <button
              type="button"
              className={styles.reintentar}
              onClick={() => {
                void cargarPrimera();
              }}
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {!esOdontologo && estado === "success" && (
        <>
          {error !== null && (
            <div className={styles.alerta} role="alert">
              <p>{error.message}</p>
              {error.kind !== "forbidden" && (
                <button
                  type="button"
                  className={styles.reintentar}
                  onClick={() => {
                    if (cursor !== null) {
                      void cargarMas();
                    } else {
                      void cargarPrimera();
                    }
                  }}
                >
                  Reintentar
                </button>
              )}
            </div>
          )}

          {aviso !== null && (
            <p className={styles.aviso} role="status">
              {aviso}
            </p>
          )}

          {items.length === 0 ? (
            <p className={styles.estado}>No hay notificaciones fallidas.</p>
          ) : (
            <ul className={styles.lista} aria-label="Notificaciones fallidas">
              {items.map((item) => (
                <li key={item.id} className={styles.item}>
                  <p className={styles.principal}>
                    <strong>{item.tipo}</strong> · {item.intentos} intento
                    {item.intentos === 1 ? "" : "s"}
                  </p>
                  <p className={styles.detalle}>
                    Error: {item.error ?? "—"}
                  </p>
                  <p className={styles.detalle}>
                    Envío:{" "}
                    {item.enviar_en === null
                      ? "—"
                      : formatearFechaHora(item.enviar_en)}
                  </p>
                  <p className={styles.detalle}>
                    Paciente: {item.paciente_nombre ?? "—"} (
                    {item.paciente_email ?? "—"})
                  </p>
                  <p className={styles.detalle}>
                    Turno: {formatearFechaHora(item.inicio)}–
                    {formatearHora(item.fin)}
                  </p>
                </li>
              ))}
            </ul>
          )}

          {cursor !== null && (
            <button
              type="button"
              className={styles.cargarMas}
              disabled={cargandoMas}
              onClick={() => {
                void cargarMas();
              }}
            >
              {cargandoMas ? "Cargando…" : "Cargar más"}
            </button>
          )}
        </>
      )}
    </section>
  );
}

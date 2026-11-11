/**
 * Página pública `/cancelar?token=<token>&id=<id>` (C-06 es DELETE-only).
 * Confirmación genérica sin datos del turno; el token es la única credencial
 * y el id solo un localizador opaco.
 */

import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  ApiError,
  ApiHttpError,
  isMensajeDetail,
} from "../shared/api/client";
import {
  cancelarTurno,
  type CancelacionOut,
} from "../shared/api/reserva";
import { mensajeEspera } from "../features/reserva/errores";
import styles from "./Cancelar.module.css";

const MENSAJE_GENERICO =
  "Este link no es válido. Si necesitás cancelar un turno, contactá al consultorio.";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MENSAJE_RED =
  "No pudimos conectarnos. Revisá tu conexión e intentá de nuevo.";
const MENSAJE_INESPERADO =
  "La respuesta del servidor no es válida. Intentá de nuevo.";

type Estado =
  | { tipo: "confirmar" }
  | { tipo: "enviando" }
  | { tipo: "exito"; cancelacion: CancelacionOut }
  | {
      tipo: "error";
      mensaje: string;
      contacto?: string;
      reintentar: boolean;
    };

export function Cancelar(): JSX.Element {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const id = searchParams.get("id") ?? "";
  const linkValido = token !== "" && UUID_RE.test(id);

  const [estado, setEstado] = useState<Estado>({ tipo: "confirmar" });

  const cancelar = async (): Promise<void> => {
    if (!linkValido) {
      return;
    }
    setEstado({ tipo: "enviando" });
    try {
      const cancelacion = await cancelarTurno(id, token);
      setEstado({ tipo: "exito", cancelacion });
    } catch (err: unknown) {
      if (err instanceof ApiHttpError) {
        if (err.status === 422 && isMensajeDetail(err.detail)) {
          const detalle = err.detail;
          const conContacto = detalle.codigo === "cancelacion_fuera_de_plazo";
          setEstado({
            tipo: "error",
            mensaje: detalle.mensaje,
            ...(conContacto && detalle.contacto !== undefined
              ? { contacto: detalle.contacto }
              : {}),
            reintentar: false,
          });
          return;
        }
        if (err.status === 403 || err.status === 404) {
          setEstado({
            tipo: "error",
            mensaje: MENSAJE_GENERICO,
            reintentar: false,
          });
          return;
        }
        if (err.status === 429) {
          setEstado({
            tipo: "error",
            mensaje: mensajeEspera(err.retryAfter),
            reintentar: false,
          });
          return;
        }
      }
      if (err instanceof ApiError && err.code === "NETWORK_ERROR") {
        setEstado({
          tipo: "error",
          mensaje: MENSAJE_RED,
          reintentar: true,
        });
        return;
      }
      setEstado({
        tipo: "error",
        mensaje: MENSAJE_INESPERADO,
        reintentar: true,
      });
    }
  };

  if (!linkValido) {
    return (
      <main className={styles.pagina}>
        <h1 className={styles.titulo}>Cancelar turno</h1>
        <p className={styles.alertaTexto} role="alert">
          {MENSAJE_GENERICO}
        </p>
      </main>
    );
  }

  return (
    <main className={styles.pagina}>
      <h1 className={styles.titulo}>Cancelar turno</h1>

      {(estado.tipo === "confirmar" || estado.tipo === "enviando") && (
        <section className={styles.tarjeta} aria-label="Confirmar cancelación">
          <p className={styles.parrafo}>¿Querés cancelar este turno?</p>
          <p className={styles.parrafo}>
            La cancelación es definitiva. Si tenés dudas, contactá al
            consultorio.
          </p>
          <button
            type="button"
            className={styles.boton}
            disabled={estado.tipo === "enviando"}
            onClick={() => {
              void cancelar();
            }}
          >
            {estado.tipo === "enviando"
              ? "Cancelando…"
              : "Confirmar cancelación"}
          </button>
        </section>
      )}

      {estado.tipo === "error" && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{estado.mensaje}</p>
          {estado.contacto !== undefined && (
            <p className={styles.parrafo}>
              Contacto:{" "}
              <a href={`mailto:${estado.contacto}`}>{estado.contacto}</a>
            </p>
          )}
          {estado.reintentar && (
            <button
              type="button"
              className={styles.botonSecundario}
              onClick={() => {
                void cancelar();
              }}
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {estado.tipo === "exito" && (
        <section
          className={styles.tarjeta}
          aria-label="Cancelación confirmada"
          role="status"
        >
          <h2 className={styles.subtitulo}>Cancelación confirmada</h2>
          <p className={styles.parrafo}>{estado.cancelacion.mensaje}</p>
          <p className={styles.parrafo}>
            Estado del turno: {estado.cancelacion.estado}
          </p>
        </section>
      )}
    </main>
  );
}

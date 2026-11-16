/**
 * Panel de detalle de un turno abierto en estado de la página (sin URL):
 * estado, origen, horario, duración, profesional y paciente; historial
 * paginado; corrección de datos y transiciones de estado válidas, más las
 * acciones de reprogramar y cancelar (§6.1, §7, §8, D-2/D-9/D-11).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiHttpError } from "../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../shared/api/errores";
import {
  cambiarEstado,
  getFicha,
  type AuditoriaItem,
  type ReprogramacionOut,
  type TurnoFichaOut,
} from "../../../shared/api/staff";
import {
  formatearDuracion,
  formatearHora,
} from "../../../shared/format";
import {
  puedeCancelar,
  puedeCorregirPaciente,
  puedeReprogramar,
  transicionesPermitidas,
  type TransicionEstado,
} from "../agenda/estados";
import { useExpirarSesion, useStaffSesion } from "../sesion";
import { CancelarTurnoForm } from "./CancelarTurnoForm";
import { CorregirPacienteForm } from "./CorregirPacienteForm";
import { HistorialTurno } from "./HistorialTurno";
import { ReprogramarTurnoForm } from "./ReprogramarTurnoForm";
import styles from "./TurnoDetalle.module.css";

type EstadoDetalle = "loading" | "success" | "error";
type Operacion = "reprogramar" | "cancelar" | "corregir" | null;

interface TurnoDetalleProps {
  turnoId: string;
  profesionalId: string;
  granularidad: number;
  onCerrar: (mensaje?: string) => void;
  onTurnoActualizado: (inicio?: string) => void;
}

function deduplicar(items: AuditoriaItem[]): AuditoriaItem[] {
  const vistos = new Set<string>();
  const unicos: AuditoriaItem[] = [];
  for (const item of items) {
    if (vistos.has(item.id)) {
      continue;
    }
    vistos.add(item.id);
    unicos.push(item);
  }
  return unicos;
}

export function TurnoDetalle({
  turnoId,
  profesionalId,
  granularidad,
  onCerrar,
  onTurnoActualizado,
}: TurnoDetalleProps): JSX.Element {
  const sesion = useStaffSesion();
  const expirarSesion = useExpirarSesion();
  const [estado, setEstado] = useState<EstadoDetalle>("loading");
  const [ficha, setFicha] = useState<TurnoFichaOut | null>(null);
  const [error, setError] = useState<StaffErrorInfo | null>(null);
  const [operacion, setOperacion] = useState<Operacion>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [errorOperacion, setErrorOperacion] = useState<string | null>(null);
  const [historial, setHistorial] = useState<AuditoriaItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);
  const [errorHistorial, setErrorHistorial] = useState<string | null>(null);
  const [estadoPendiente, setEstadoPendiente] =
    useState<TransicionEstado | null>(null);
  const tituloRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let activo = true;
    setEstado("loading");
    setFicha(null);
    setError(null);
    setAviso(null);
    setErrorOperacion(null);
    setHistorial([]);
    setCursor(null);
    setErrorHistorial(null);
    getFicha(turnoId)
      .then((data) => {
        if (!activo) {
          return;
        }
        setFicha(data);
        setHistorial(deduplicar(data.auditoria.items));
        setCursor(data.auditoria.next_cursor);
        setEstado("success");
      })
      .catch((err: unknown) => {
        if (!activo) {
          return;
        }
        if (err instanceof ApiHttpError && err.status === 401) {
          expirarSesion();
          return;
        }
        setError(mensajeDeError(err, "la ficha del turno"));
        setEstado("error");
      });
    return () => {
      activo = false;
    };
  }, [turnoId, expirarSesion]);

  useEffect(() => {
    if (estado === "success") {
      tituloRef.current?.focus();
    }
  }, [estado]);

  const recargarFicha = useCallback(async (): Promise<boolean> => {
    try {
      const data = await getFicha(turnoId);
      setFicha(data);
      setHistorial(deduplicar(data.auditoria.items));
      setCursor(data.auditoria.next_cursor);
      setErrorHistorial(null);
      return true;
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return false;
      }
      if (err instanceof ApiHttpError && err.status === 404) {
        onCerrar("El turno ya no está disponible.");
        onTurnoActualizado();
        return false;
      }
      return false;
    }
  }, [turnoId, expirarSesion, onCerrar, onTurnoActualizado]);

  const reprogramado = async (out: ReprogramacionOut): Promise<void> => {
    setOperacion(null);
    const recargada = await recargarFicha();
    if (!recargada) {
      return;
    }
    setAviso("Turno reprogramado.");
    onTurnoActualizado(out.inicio);
  };

  const cancelado = async (): Promise<void> => {
    setOperacion(null);
    const recargada = await recargarFicha();
    if (!recargada) {
      return;
    }
    setAviso("Turno cancelado.");
    onTurnoActualizado();
  };

  const estadoTerminal = async (mensaje: string): Promise<void> => {
    setOperacion(null);
    setAviso(mensaje);
    await recargarFicha();
    onTurnoActualizado();
  };

  const pacienteCorregido = async (): Promise<void> => {
    setOperacion(null);
    const recargada = await recargarFicha();
    if (!recargada) {
      return;
    }
    setAviso("Datos del paciente corregidos.");
  };

  const aplicarEstado = async (nuevo: TransicionEstado): Promise<void> => {
    if (ficha === null || estadoPendiente !== null) {
      return;
    }
    setEstadoPendiente(nuevo);
    setErrorOperacion(null);
    setAviso(null);
    try {
      const out = await cambiarEstado(ficha.id, nuevo);
      const recargada = await recargarFicha();
      if (!recargada) {
        return;
      }
      setAviso(`Estado actualizado a ${out.estado}.`);
      onTurnoActualizado();
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const info = mensajeDeError(err, "el cambio de estado");
      if (info.kind === "validation" && info.codigo === "transicion_invalida") {
        setErrorOperacion(info.message);
        await recargarFicha();
        onTurnoActualizado();
        return;
      }
      setErrorOperacion(info.message);
    } finally {
      setEstadoPendiente(null);
    }
  };

  const verMasHistorial = async (): Promise<void> => {
    if (cursor === null || cargandoHistorial) {
      return;
    }
    setCargandoHistorial(true);
    setErrorHistorial(null);
    try {
      const data = await getFicha(turnoId, cursor);
      setHistorial((previos) =>
        deduplicar([...previos, ...data.auditoria.items]),
      );
      setCursor(data.auditoria.next_cursor);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      if (err instanceof ApiHttpError && err.status === 400) {
        setErrorHistorial(
          "El historial se reinició porque el cursor dejó de ser válido.",
        );
        try {
          const data = await getFicha(turnoId);
          setHistorial(deduplicar(data.auditoria.items));
          setCursor(data.auditoria.next_cursor);
        } catch {
          setHistorial([]);
          setCursor(null);
        }
        return;
      }
      setErrorHistorial(mensajeDeError(err, "el historial").message);
    } finally {
      setCargandoHistorial(false);
    }
  };

  const rol = sesion.rol;
  const mostrarReprogramar =
    ficha !== null && puedeReprogramar(ficha.estado, rol);
  const mostrarCancelar = ficha !== null && puedeCancelar(ficha.estado, rol);
  const mostrarCorregir = ficha !== null && puedeCorregirPaciente(rol);
  const transiciones =
    ficha === null ? [] : transicionesPermitidas(ficha.estado, rol);
  const hayAcciones =
    mostrarReprogramar ||
    mostrarCancelar ||
    mostrarCorregir ||
    transiciones.length > 0;
  const accionesDeshabilitadas = estadoPendiente !== null;

  return (
    <section className={styles.panel} aria-label="Detalle del turno">
      <div className={styles.encabezado}>
        <h2 className={styles.titulo} ref={tituloRef} tabIndex={-1}>
          Detalle del turno
        </h2>
        <button type="button" className={styles.cerrar} onClick={() => onCerrar()}>
          Cerrar detalle
        </button>
      </div>

      {estado === "loading" && (
        <p className={styles.estado} role="status">
          Cargando detalle…
        </p>
      )}

      {estado === "error" && error !== null && (
        <p className={styles.error} role="alert">
          {error.message}
        </p>
      )}

      {estado === "success" && ficha !== null && (
        <>
          <dl className={styles.datos}>
            <dt>Estado</dt>
            <dd>{ficha.estado}</dd>
            <dt>Origen</dt>
            <dd>{ficha.origen}</dd>
            <dt>Horario</dt>
            <dd>
              {formatearHora(ficha.inicio)}–{formatearHora(ficha.fin)}
            </dd>
            <dt>Duración</dt>
            <dd>{formatearDuracion(ficha.duracion_min)}</dd>
            <dt>Profesional</dt>
            <dd>{ficha.profesional.nombre}</dd>
            <dt>Paciente</dt>
            <dd>{ficha.paciente.nombre ?? "—"}</dd>
            <dt>DNI</dt>
            <dd>{ficha.paciente.dni ?? "—"}</dd>
            <dt>Teléfono</dt>
            <dd>{ficha.paciente.telefono ?? "—"}</dd>
            <dt>Email</dt>
            <dd>{ficha.paciente.email ?? "—"}</dd>
            <dt>Obra social</dt>
            <dd>{ficha.paciente.obra_social ?? "—"}</dd>
          </dl>

          {aviso !== null && (
            <p className={styles.aviso} role="status">
              {aviso}
            </p>
          )}

          {errorOperacion !== null && (
            <p className={styles.alerta} role="alert">
              {errorOperacion}
            </p>
          )}

          {hayAcciones && operacion === null && (
            <div
              className={styles.acciones}
              role="group"
              aria-label="Acciones del turno"
            >
              {transiciones.map((transicion) => (
                <button
                  key={transicion.estado}
                  type="button"
                  className={styles.accion}
                  disabled={accionesDeshabilitadas}
                  onClick={() => {
                    void aplicarEstado(transicion.estado);
                  }}
                >
                  {estadoPendiente === transicion.estado
                    ? "Guardando…"
                    : transicion.etiqueta}
                </button>
              ))}
              {mostrarReprogramar && (
                <button
                  type="button"
                  className={styles.accion}
                  disabled={accionesDeshabilitadas}
                  onClick={() => {
                    setAviso(null);
                    setErrorOperacion(null);
                    setOperacion("reprogramar");
                  }}
                >
                  Reprogramar turno
                </button>
              )}
              {mostrarCancelar && (
                <button
                  type="button"
                  className={styles.accion}
                  disabled={accionesDeshabilitadas}
                  onClick={() => {
                    setAviso(null);
                    setErrorOperacion(null);
                    setOperacion("cancelar");
                  }}
                >
                  Cancelar turno
                </button>
              )}
              {mostrarCorregir && (
                <button
                  type="button"
                  className={styles.accion}
                  disabled={accionesDeshabilitadas}
                  onClick={() => {
                    setAviso(null);
                    setErrorOperacion(null);
                    setOperacion("corregir");
                  }}
                >
                  Corregir datos del paciente
                </button>
              )}
            </div>
          )}

          {operacion === "reprogramar" && (
            <ReprogramarTurnoForm
              turnoId={ficha.id}
              profesionalId={profesionalId}
              granularidad={granularidad}
              ficha={ficha}
              onReprogramado={reprogramado}
              onNoEditable={estadoTerminal}
              onCancelar={() => setOperacion(null)}
            />
          )}

          {operacion === "cancelar" && (
            <CancelarTurnoForm
              turnoId={ficha.id}
              ficha={ficha}
              onCancelado={cancelado}
              onEstadoTerminal={estadoTerminal}
              onCancelar={() => setOperacion(null)}
            />
          )}

          {operacion === "corregir" && (
            <CorregirPacienteForm
              turnoId={ficha.id}
              paciente={ficha.paciente}
              onCorregido={pacienteCorregido}
              onCancelar={() => setOperacion(null)}
            />
          )}

          <HistorialTurno
            items={historial}
            nextCursor={cursor}
            cargando={cargandoHistorial}
            error={errorHistorial}
            onVerMas={() => {
              void verMasHistorial();
            }}
          />
        </>
      )}
    </section>
  );
}

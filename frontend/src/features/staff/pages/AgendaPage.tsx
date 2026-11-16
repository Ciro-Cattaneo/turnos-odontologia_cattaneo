/**
 * Agenda staff día/semana por profesional: selector, navegación de fecha,
 * franjas tipificadas, cerrados del día y frescura visible (D-5, D-15).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiHttpError } from "../../../shared/api/client";
import { mensajeDeError } from "../../../shared/api/errores";
import type { Profesional } from "../../../shared/api/reserva";
import {
  getProfesionalesStaff,
  type FranjaLibre,
  type TurnoStaffOut,
  type VistaAgenda,
} from "../../../shared/api/staff";
import {
  addDias,
  fechaEnConsultorio,
  formatearFechaCalendario,
  formatearFechaHora,
  hoyEnConsultorio,
} from "../../../shared/format";
import { useAgenda } from "../agenda/useAgenda";
import { AgendaDia } from "../components/AgendaDia";
import { AgendaError } from "../components/AgendaError";
import { AltaTurnoForm } from "../components/AltaTurnoForm";
import { ProfesionalSelector } from "../components/ProfesionalSelector";
import { TurnoDetalle } from "../components/TurnoDetalle";
import { useExpirarSesion, useStaffSesion } from "../sesion";
import styles from "../components/Agenda.module.css";

export function AgendaPage(): JSX.Element {
  const sesion = useStaffSesion();
  const expirarSesion = useExpirarSesion();

  const [profesionales, setProfesionales] = useState<Profesional[] | null>(null);
  const [cargandoProfesionales, setCargandoProfesionales] = useState(true);
  const [errorProfesionales, setErrorProfesionales] = useState<string | null>(
    null,
  );
  const [seleccionManual, setSeleccionManual] = useState<string | null>(null);
  const [vista, setVista] = useState<VistaAgenda>("dia");
  const [fecha, setFecha] = useState<string>(() => hoyEnConsultorio());
  const [detalleTurnoId, setDetalleTurnoId] = useState<string | null>(null);
  const [altaFranja, setAltaFranja] = useState<FranjaLibre | null>(null);
  const [avisoAlta, setAvisoAlta] = useState<string | null>(null);
  const [avisoAgenda, setAvisoAgenda] = useState<string | null>(null);

  const cargarProfesionales = useCallback(async () => {
    setCargandoProfesionales(true);
    setErrorProfesionales(null);
    try {
      const items = await getProfesionalesStaff();
      setProfesionales(items);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      setErrorProfesionales(mensajeDeError(err, "la agenda").message);
    } finally {
      setCargandoProfesionales(false);
    }
  }, [expirarSesion]);

  useEffect(() => {
    void cargarProfesionales();
  }, [cargarProfesionales]);

  const profesionalesVisibles: Profesional[] =
    profesionales === null
      ? []
      : sesion.rol === "odontologo"
        ? profesionales.filter((item) => item.id === sesion.profesional_id)
        : profesionales;

  const seleccionValida =
    seleccionManual !== null &&
    profesionalesVisibles.some((item) => item.id === seleccionManual)
      ? seleccionManual
      : null;
  const seleccionado = seleccionValida ?? profesionalesVisibles[0]?.id ?? null;
  const profesionalSeleccionado =
    profesionalesVisibles.find((item) => item.id === seleccionado) ?? null;
  const puedeCrear = sesion.rol === "recepcion" || sesion.rol === "admin";

  const agenda = useAgenda({ profesionalId: seleccionado, vista, fecha });

  const actualizar = (): void => {
    if (seleccionado === null) {
      void cargarProfesionales();
      return;
    }
    agenda.actualizar();
  };

  const recargarProfesionales = (): void => {
    void cargarProfesionales();
    agenda.actualizar();
  };

  const abrirDetalle = (turnoId: string): void => {
    setAltaFranja(null);
    setAvisoAgenda(null);
    setDetalleTurnoId(turnoId);
  };

  const cerrarDetalle = (mensaje?: string): void => {
    setDetalleTurnoId(null);
    if (mensaje !== undefined) {
      setAvisoAgenda(mensaje);
    }
  };

  const abrirAlta = (franja: FranjaLibre): void => {
    setDetalleTurnoId(null);
    setAvisoAlta(null);
    setAltaFranja(franja);
  };

  const cerrarPaneles = (): void => {
    setDetalleTurnoId(null);
    setAltaFranja(null);
  };

  const cambiarProfesional = (id: string): void => {
    setSeleccionManual(id);
    cerrarPaneles();
  };

  const cambiarVista = (nueva: VistaAgenda): void => {
    setVista(nueva);
    cerrarPaneles();
  };

  const cambiarFecha = (nueva: string): void => {
    setFecha(nueva);
    cerrarPaneles();
  };

  const turnoCreado = (turno: TurnoStaffOut): void => {
    setAltaFranja(null);
    setAvisoAlta(
      turno.notificaciones_encoladas
        ? "Turno creado. La agenda se actualizó."
        : "El turno quedó creado, pero no se pudieron encolar los mails. Contactá al consultorio.",
    );
    agenda.actualizar();
  };

  const turnoActualizado = (inicio?: string): void => {
    if (seleccionado !== null) {
      agenda.invalidar(seleccionado, "dia", fecha);
      if (inicio !== undefined) {
        agenda.invalidar(
          seleccionado,
          "dia",
          fechaEnConsultorio(new Date(inicio)),
        );
      }
    }
    agenda.actualizar();
  };

  const paso = vista === "dia" ? 1 : 7;
  const etiquetaAnterior = vista === "dia" ? "Día anterior" : "Semana anterior";
  const etiquetaSiguiente =
    vista === "dia" ? "Día siguiente" : "Semana siguiente";

  return (
    <section className={styles.pagina} aria-labelledby="titulo-agenda">
      <div className={styles.encabezado}>
        <h1 className={styles.titulo} id="titulo-agenda">
          {sesion.rol === "odontologo" ? "Mi agenda" : "Agenda"}
        </h1>
        <button
          type="button"
          className={styles.actualizar}
          disabled={cargandoProfesionales || agenda.estado.status === "loading"}
          onClick={actualizar}
        >
          Actualizar
        </button>
      </div>

      {errorProfesionales !== null && (
        <div className={styles.alerta} role="alert">
          <p>{errorProfesionales}</p>
          <button
            type="button"
            className={styles.reintentar}
            onClick={() => {
              void cargarProfesionales();
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {avisoAlta !== null && (
        <p className={styles.aviso} role="status">
          {avisoAlta}
        </p>
      )}

      {avisoAgenda !== null && (
        <p className={styles.aviso} role="status">
          {avisoAgenda}
        </p>
      )}

      {cargandoProfesionales && (
        <p className={styles.estado} role="status">
          Cargando agenda…
        </p>
      )}

      {profesionales !== null && (
        <p className={styles.estado}>Profesionales: {profesionales.length}</p>
      )}

      {profesionales !== null && (
        <ProfesionalSelector
          profesionales={profesionalesVisibles}
          value={seleccionado ?? ""}
          onChange={cambiarProfesional}
        />
      )}

      {seleccionado !== null && (
        <>
          <div
            className={styles.controles}
            role="group"
            aria-label="Vista de agenda"
          >
            <button
              type="button"
              className={styles.botonVista}
              aria-pressed={vista === "dia"}
              onClick={() => cambiarVista("dia")}
            >
              Día
            </button>
            <button
              type="button"
              className={styles.botonVista}
              aria-pressed={vista === "semana"}
              onClick={() => cambiarVista("semana")}
            >
              Semana
            </button>
          </div>

          <div className={styles.navegacionFecha}>
            <button
              type="button"
              className={styles.boton}
              onClick={() => cambiarFecha(addDias(fecha, -paso))}
            >
              {etiquetaAnterior}
            </button>
            <time className={styles.fechaActual} dateTime={fecha}>
              {formatearFechaCalendario(fecha)}
            </time>
            <button
              type="button"
              className={styles.boton}
              onClick={() => cambiarFecha(addDias(fecha, paso))}
            >
              {etiquetaSiguiente}
            </button>
          </div>

          {agenda.estado.status === "loading" && (
            <p className={styles.estado} role="status">
              Cargando agenda…
            </p>
          )}

          {agenda.estado.status === "error" && agenda.estado.error !== null && (
            <AgendaError
              info={agenda.estado.error}
              onReintentar={agenda.reintentar}
              onRecargarProfesionales={recargarProfesionales}
            />
          )}

          {agenda.estado.status === "success" &&
            agenda.estado.agenda !== null && (
              <>
                <p className={styles.actualizacion}>
                  Última actualización:{" "}
                  {agenda.estado.agenda.ultima_actualizacion === null
                    ? "sin datos cargados"
                    : formatearFechaHora(
                        agenda.estado.agenda.ultima_actualizacion,
                      )}
                </p>
                {agenda.estado.agenda.dias.map((dia) => (
                  <AgendaDia
                    key={dia.fecha}
                    dia={dia}
                    puedeCrear={puedeCrear}
                    onAbrirTurno={abrirDetalle}
                    onCrearTurno={abrirAlta}
                  />
                ))}
              </>
            )}
        </>
      )}

      {detalleTurnoId !== null && profesionalSeleccionado !== null && (
        <TurnoDetalle
          turnoId={detalleTurnoId}
          profesionalId={profesionalSeleccionado.id}
          granularidad={profesionalSeleccionado.duracion_default_min}
          onCerrar={cerrarDetalle}
          onTurnoActualizado={turnoActualizado}
        />
      )}

      {altaFranja !== null &&
        puedeCrear &&
        profesionalSeleccionado !== null && (
          <AltaTurnoForm
            profesionalId={profesionalSeleccionado.id}
            profesionalNombre={profesionalSeleccionado.nombre}
            franja={altaFranja}
            granularidad={profesionalSeleccionado.duracion_default_min}
            onCreado={turnoCreado}
            onCancelar={() => setAltaFranja(null)}
            onRefrescarAgenda={agenda.actualizar}
          />
        )}
    </section>
  );
}

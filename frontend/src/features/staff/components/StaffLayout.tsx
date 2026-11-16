/**
 * Layout protegido de staff: resuelve `GET /api/auth/me` una vez, comparte la
 * sesión acotada y redirige a `/staff/login` ante `401` (D-2, D-3).
 */

import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, Outlet } from "react-router-dom";

import { ApiHttpError } from "../../../shared/api/client";
import { mensajeDeError } from "../../../shared/api/errores";
import { logout, me, type MeOut } from "../../../shared/api/staff";
import { StaffSesionProvider, type AvisoSesion } from "../sesion";
import styles from "./StaffLayout.module.css";

type EstadoSesion = "cargando" | "activa" | "sin_sesion" | "error";

const NAVEGACION_NOTIFICACIONES: ReadonlySet<string> = new Set([
  "recepcion",
  "admin",
]);

export function StaffLayout(): JSX.Element {
  const [estado, setEstado] = useState<EstadoSesion>("cargando");
  const [sesion, setSesion] = useState<MeOut | null>(null);
  const [aviso, setAviso] = useState<AvisoSesion | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [errorCierre, setErrorCierre] = useState<string | null>(null);
  const [cerrando, setCerrando] = useState(false);

  const resolverSesion = useCallback(async () => {
    setEstado("cargando");
    setErrorCarga(null);
    try {
      const identidad = await me();
      setSesion(identidad);
      setAviso(null);
      setEstado("activa");
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        setSesion(null);
        setEstado("sin_sesion");
        return;
      }
      setErrorCarga(mensajeDeError(err, "el inicio de sesión").message);
      setEstado("error");
    }
  }, []);

  useEffect(() => {
    void resolverSesion();
  }, [resolverSesion]);

  const expirarSesion = useCallback(() => {
    setSesion(null);
    setAviso("sesion_expirada");
    setEstado("sin_sesion");
  }, []);

  const cerrarSesion = useCallback(async () => {
    setCerrando(true);
    setErrorCierre(null);
    try {
      await logout();
      setSesion(null);
      setAviso(null);
      setEstado("sin_sesion");
    } catch (err: unknown) {
      setErrorCierre(mensajeDeError(err, "el cierre de sesión").message);
    } finally {
      setCerrando(false);
    }
  }, []);

  if (estado === "cargando") {
    return (
      <main className={styles.contenido}>
        <p role="status">Verificando sesión…</p>
      </main>
    );
  }

  if (estado === "error") {
    return (
      <main className={styles.contenido}>
        <div role="alert">
          <p className={styles.alerta}>{errorCarga}</p>
          <button
            type="button"
            className={styles.botonSecundario}
            onClick={() => {
              void resolverSesion();
            }}
          >
            Reintentar
          </button>
        </div>
      </main>
    );
  }

  if (estado === "sin_sesion" || sesion === null) {
    return (
      <Navigate
        to="/staff/login"
        replace
        state={aviso === null ? null : { aviso }}
      />
    );
  }

  return (
    <div className={styles.layout}>
      <header className={styles.encabezado}>
        <nav className={styles.navegacion} aria-label="Navegación staff">
          <Link className={styles.enlace} to="/staff/agenda">
            Agenda
          </Link>
          {NAVEGACION_NOTIFICACIONES.has(sesion.rol) && (
            <Link className={styles.enlace} to="/staff/notificaciones">
              Notificaciones fallidas
            </Link>
          )}
          {sesion.rol === "admin" && (
            <>
              <Link className={styles.enlace} to="/staff/admin/profesionales">
                Profesionales
              </Link>
              <Link className={styles.enlace} to="/staff/admin/usuarios">
                Usuarios staff
              </Link>
              <Link className={styles.enlace} to="/staff/admin/reportes">
                Reportes
              </Link>
            </>
          )}
        </nav>
        <div className={styles.identidad}>
          <span className={styles.email}>{sesion.email}</span>
          <button
            type="button"
            className={styles.salir}
            disabled={cerrando}
            onClick={() => {
              void cerrarSesion();
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </header>
      {errorCierre !== null && (
        <p className={styles.alerta} role="alert">
          {errorCierre}
        </p>
      )}
      <main className={styles.contenido}>
        <StaffSesionProvider sesion={sesion} onExpirar={expirarSesion}>
          <Outlet />
        </StaffSesionProvider>
      </main>
    </div>
  );
}

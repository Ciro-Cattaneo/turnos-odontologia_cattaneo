/**
 * Administración de usuarios staff (D-1/D-7): listado keyset con "Cargar más",
 * alta con invariante de rol, edición sin email/password, baja lógica y
 * reactivación, con gating por rol y errores accionables (SA R1–R5).
 */

import { useCallback, useState } from "react";

import {
  actualizarUsuarioStaff,
  darDeBajaUsuarioStaff,
  type UsuarioStaff,
} from "../../../../shared/api/admin";
import { ApiHttpError } from "../../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import type { StaffRol } from "../../../../shared/api/staff";
import { useExpirarSesion } from "../../sesion";
import { AltaUsuarioForm } from "../components/AltaUsuarioForm";
import { EditarUsuarioForm } from "../components/EditarUsuarioForm";
import { SinPermisoAdmin } from "../components/SinPermisoAdmin";
import { useUsuariosStaffAdmin } from "../hooks/useUsuariosStaffAdmin";
import { useSesionAdmin } from "../useSesionAdmin";
import styles from "./AdminUsuariosPage.module.css";

type ModoFormulario = "alta" | "editar" | null;

function etiquetaRol(rol: StaffRol): string {
  if (rol === "recepcion") {
    return "Recepción";
  }
  if (rol === "odontologo") {
    return "Odontólogo";
  }
  return "Admin";
}

export function AdminUsuariosPage(): JSX.Element {
  const { esAdmin } = useSesionAdmin();

  if (!esAdmin) {
    return <SinPermisoAdmin />;
  }

  return <UsuariosAdminContenido />;
}

function UsuariosAdminContenido(): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const {
    estado,
    items,
    profesionales,
    error,
    nextCursor,
    cargandoMas,
    refrescar,
    cargarMas,
    reemplazar,
  } = useUsuariosStaffAdmin();

  const [modo, setModo] = useState<ModoFormulario>(null);
  const [seleccionado, setSeleccionado] = useState<UsuarioStaff | null>(null);
  const [confirmarBaja, setConfirmarBaja] = useState<string | null>(null);
  const [mutando, setMutando] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [errorMutacion, setErrorMutacion] = useState<StaffErrorInfo | null>(
    null,
  );

  const cerrarFormulario = useCallback((): void => {
    setModo(null);
    setSeleccionado(null);
  }, []);

  const alCreado = useCallback((): void => {
    setModo(null);
    setAviso("Usuario creado.");
    void refrescar();
  }, [refrescar]);

  const alActualizado = useCallback(
    (usuario: UsuarioStaff): void => {
      cerrarFormulario();
      reemplazar(usuario);
      setAviso("Usuario actualizado.");
    },
    [cerrarFormulario, reemplazar],
  );

  const alNoEncontrado = useCallback((): void => {
    cerrarFormulario();
    setAviso("El usuario ya no está disponible.");
    void refrescar();
  }, [cerrarFormulario, refrescar]);

  const manejarError = (err: unknown): void => {
    if (err instanceof ApiHttpError && err.status === 401) {
      expirarSesion();
      return;
    }
    setErrorMutacion(mensajeDeError(err, "la operación del usuario staff"));
  };

  const darDeBaja = async (usuario: UsuarioStaff): Promise<void> => {
    setMutando(usuario.id);
    setErrorMutacion(null);
    try {
      const actualizado = await darDeBajaUsuarioStaff(usuario.id);
      reemplazar(actualizado);
      setConfirmarBaja(null);
      setAviso("Usuario dado de baja.");
    } catch (err: unknown) {
      manejarError(err);
    } finally {
      setMutando(null);
    }
  };

  const reactivar = async (usuario: UsuarioStaff): Promise<void> => {
    setMutando(usuario.id);
    setErrorMutacion(null);
    try {
      const actualizado = await actualizarUsuarioStaff(usuario.id, {
        activo: true,
      });
      reemplazar(actualizado);
      setAviso("Usuario reactivado.");
    } catch (err: unknown) {
      manejarError(err);
    } finally {
      setMutando(null);
    }
  };

  const abrirEdicion = (usuario: UsuarioStaff): void => {
    setSeleccionado(usuario);
    setModo("editar");
    setConfirmarBaja(null);
  };

  const nombreProfesional = (id: string): string =>
    profesionales.find((profesional) => profesional.id === id)?.nombre ?? "—";

  return (
    <section className={styles.pagina} aria-labelledby="titulo-usuarios-staff">
      <div className={styles.encabezado}>
        <h1 className={styles.titulo} id="titulo-usuarios-staff">
          Usuarios staff
        </h1>
        {modo === null && (
          <button
            type="button"
            className={styles.accion}
            onClick={() => {
              setModo("alta");
              setSeleccionado(null);
              setConfirmarBaja(null);
            }}
          >
            Agregar usuario
          </button>
        )}
      </div>

      <p className={styles.aviso} role="status" aria-live="polite">
        {aviso ?? ""}
      </p>

      {errorMutacion !== null && (
        <p className={styles.alerta} role="alert">
          {errorMutacion.message}
        </p>
      )}

      {modo === "alta" && (
        <AltaUsuarioForm
          profesionales={profesionales}
          onCreado={alCreado}
          onCancelar={cerrarFormulario}
        />
      )}

      {modo === "editar" && seleccionado !== null && (
        <EditarUsuarioForm
          usuario={seleccionado}
          profesionales={profesionales}
          onActualizado={alActualizado}
          onNoEncontrado={alNoEncontrado}
          onCancelar={cerrarFormulario}
        />
      )}

      {estado === "cargando" && (
        <p className={styles.estado} role="status">
          Cargando usuarios staff.
        </p>
      )}

      {estado === "error" && error !== null && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{error.message}</p>
          {error.kind !== "forbidden" && (
            <button
              type="button"
              className={styles.secundario}
              onClick={() => {
                void refrescar();
              }}
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {estado === "listo" && error !== null && (
        <div className={styles.alerta} role="alert">
          <p className={styles.alertaTexto}>{error.message}</p>
          <button
            type="button"
            className={styles.secundario}
            disabled={cargandoMas}
            onClick={() => {
              void cargarMas();
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {estado === "listo" && items.length === 0 && (
        <p className={styles.estado}>No hay usuarios staff para mostrar.</p>
      )}

      {estado === "listo" && items.length > 0 && (
        <ul className={styles.lista} aria-label="Usuarios staff">
          {items.map((usuario) => (
            <li key={usuario.id} className={styles.fila}>
              <div className={styles.datos}>
                <h2 className={styles.nombre}>{usuario.email}</h2>
                <p className={styles.detalle}>
                  Rol: {etiquetaRol(usuario.rol)}
                </p>
                {usuario.profesional_id !== null && (
                  <p className={styles.detalle}>
                    Profesional: {nombreProfesional(usuario.profesional_id)}
                  </p>
                )}
                <p
                  className={usuario.activo ? styles.activo : styles.inactivo}
                >
                  {usuario.activo ? "Activo" : "Inactivo"}
                </p>
              </div>
              <div className={styles.acciones}>
                {usuario.activo ? (
                  <>
                    <button
                      type="button"
                      className={styles.secundario}
                      disabled={mutando === usuario.id}
                      onClick={() => abrirEdicion(usuario)}
                    >
                      Editar
                    </button>
                    {confirmarBaja === usuario.id ? (
                      <>
                        <button
                          type="button"
                          className={styles.accion}
                          disabled={mutando === usuario.id}
                          onClick={() => {
                            void darDeBaja(usuario);
                          }}
                        >
                          Confirmar baja
                        </button>
                        <button
                          type="button"
                          className={styles.secundario}
                          disabled={mutando === usuario.id}
                          onClick={() => setConfirmarBaja(null)}
                        >
                          Cancelar
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className={styles.secundario}
                        disabled={mutando === usuario.id}
                        onClick={() => setConfirmarBaja(usuario.id)}
                      >
                        Dar de baja
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    className={styles.accion}
                    disabled={mutando === usuario.id}
                    onClick={() => {
                      void reactivar(usuario);
                    }}
                  >
                    Reactivar
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {estado === "listo" && nextCursor !== null && (
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
    </section>
  );
}

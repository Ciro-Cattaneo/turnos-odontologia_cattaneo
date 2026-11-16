/**
 * Administración de profesionales (D-1/D-7): listado con inactivos, alta,
 * edición, baja lógica y reactivación, con gating por rol y estados de carga,
 * vacío, error y éxito en región `aria-live`.
 */

import { useCallback, useState } from "react";

import {
  actualizarProfesional,
  darDeBajaProfesional,
  type ProfesionalAdmin,
} from "../../../../shared/api/admin";
import { ApiHttpError } from "../../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import { useExpirarSesion } from "../../sesion";
import { AltaProfesionalForm } from "../components/AltaProfesionalForm";
import { EditarProfesionalForm } from "../components/EditarProfesionalForm";
import { SinPermisoAdmin } from "../components/SinPermisoAdmin";
import { useProfesionalesAdmin } from "../hooks/useProfesionalesAdmin";
import { useSesionAdmin } from "../useSesionAdmin";
import styles from "./AdminProfesionalesPage.module.css";

type ModoFormulario = "alta" | "editar" | null;

export function AdminProfesionalesPage(): JSX.Element {
  const { esAdmin } = useSesionAdmin();

  if (!esAdmin) {
    return <SinPermisoAdmin />;
  }

  return <ProfesionalesAdminContenido />;
}

function ProfesionalesAdminContenido(): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const {
    estado,
    items,
    error,
    incluirInactivos,
    cambiarIncluirInactivos,
    refrescar,
    reemplazar,
  } = useProfesionalesAdmin();

  const [modo, setModo] = useState<ModoFormulario>(null);
  const [seleccionado, setSeleccionado] = useState<ProfesionalAdmin | null>(
    null,
  );
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
    setAviso("Profesional creado.");
    void refrescar();
  }, [refrescar]);

  const alActualizado = useCallback(
    (profesional: ProfesionalAdmin): void => {
      cerrarFormulario();
      reemplazar(profesional);
      setAviso("Profesional actualizado.");
    },
    [cerrarFormulario, reemplazar],
  );

  const alNoEncontrado = useCallback((): void => {
    cerrarFormulario();
    setAviso("El profesional ya no está disponible.");
    void refrescar();
  }, [cerrarFormulario, refrescar]);

  const manejarError = (err: unknown): void => {
    if (err instanceof ApiHttpError && err.status === 401) {
      expirarSesion();
      return;
    }
    setErrorMutacion(mensajeDeError(err, "la operación del profesional"));
  };

  const darDeBaja = async (profesional: ProfesionalAdmin): Promise<void> => {
    setMutando(profesional.id);
    setErrorMutacion(null);
    try {
      const actualizado = await darDeBajaProfesional(profesional.id);
      reemplazar(actualizado);
      setConfirmarBaja(null);
      setAviso("Profesional dado de baja.");
    } catch (err: unknown) {
      manejarError(err);
    } finally {
      setMutando(null);
    }
  };

  const reactivar = async (profesional: ProfesionalAdmin): Promise<void> => {
    setMutando(profesional.id);
    setErrorMutacion(null);
    try {
      const actualizado = await actualizarProfesional(profesional.id, {
        activo: true,
      });
      reemplazar(actualizado);
      setAviso("Profesional reactivado.");
    } catch (err: unknown) {
      manejarError(err);
    } finally {
      setMutando(null);
    }
  };

  const abrirEdicion = (profesional: ProfesionalAdmin): void => {
    setSeleccionado(profesional);
    setModo("editar");
    setConfirmarBaja(null);
  };

  return (
    <section className={styles.pagina} aria-labelledby="titulo-profesionales">
      <div className={styles.encabezado}>
        <h1 className={styles.titulo} id="titulo-profesionales">
          Profesionales
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
            Agregar profesional
          </button>
        )}
      </div>

      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={incluirInactivos}
          onChange={(event) =>
            cambiarIncluirInactivos(event.target.checked)
          }
        />
        Incluir inactivos
      </label>

      <p className={styles.aviso} role="status" aria-live="polite">
        {aviso ?? ""}
      </p>

      {errorMutacion !== null && (
        <p className={styles.alerta} role="alert">
          {errorMutacion.message}
        </p>
      )}

      {modo === "alta" && (
        <AltaProfesionalForm
          onCreado={alCreado}
          onCancelar={cerrarFormulario}
        />
      )}

      {modo === "editar" && seleccionado !== null && (
        <EditarProfesionalForm
          profesional={seleccionado}
          onActualizado={alActualizado}
          onNoEncontrado={alNoEncontrado}
          onCancelar={cerrarFormulario}
        />
      )}

      {estado === "cargando" && (
        <p className={styles.estado} role="status">
          Cargando profesionales.
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

      {estado === "listo" && items.length === 0 && (
        <p className={styles.estado}>
          No hay profesionales para el filtro elegido.
        </p>
      )}

      {estado === "listo" && items.length > 0 && (
        <ul className={styles.lista} aria-label="Profesionales">
          {items.map((profesional) => (
            <li key={profesional.id} className={styles.fila}>
              <div className={styles.datos}>
                <h2 className={styles.nombre}>{profesional.nombre}</h2>
                <p className={styles.detalle}>
                  Matrícula: {profesional.matricula ?? "-"}
                </p>
                <p className={styles.detalle}>
                  Especialidad: {profesional.especialidad ?? "-"}
                </p>
                <p className={styles.detalle}>
                  Duración: {profesional.duracion_default_min} min
                </p>
                <p
                  className={
                    profesional.activo ? styles.activo : styles.inactivo
                  }
                >
                  {profesional.activo ? "Activo" : "Inactivo"}
                </p>
              </div>
              <div className={styles.acciones}>
                {profesional.activo ? (
                  <>
                    <button
                      type="button"
                      className={styles.secundario}
                      disabled={mutando === profesional.id}
                      onClick={() => abrirEdicion(profesional)}
                    >
                      Editar
                    </button>
                    {confirmarBaja === profesional.id ? (
                      <>
                        <button
                          type="button"
                          className={styles.accion}
                          disabled={mutando === profesional.id}
                          onClick={() => {
                            void darDeBaja(profesional);
                          }}
                        >
                          Confirmar baja
                        </button>
                        <button
                          type="button"
                          className={styles.secundario}
                          disabled={mutando === profesional.id}
                          onClick={() => setConfirmarBaja(null)}
                        >
                          Cancelar
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className={styles.secundario}
                        disabled={mutando === profesional.id}
                        onClick={() => setConfirmarBaja(profesional.id)}
                      >
                        Dar de baja
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    className={styles.accion}
                    disabled={mutando === profesional.id}
                    onClick={() => {
                      void reactivar(profesional);
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
    </section>
  );
}

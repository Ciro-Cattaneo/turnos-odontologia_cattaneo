/**
 * Edición de usuario staff (D-3): envía solo `rol`, `profesional_id` y
 * `activo`; el email y la contraseña nunca son editables ni viajan en el PUT.
 * Un `422 ultimo_admin` se muestra accionable sin marcar éxito.
 */

import { useEffect, useState, type FormEvent } from "react";

import {
  actualizarUsuarioStaff,
  type ProfesionalAdmin,
  type UsuarioStaff,
  type UsuarioStaffUpdateInput,
} from "../../../../shared/api/admin";
import { ApiHttpError } from "../../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import type { StaffRol } from "../../../../shared/api/staff";
import { useExpirarSesion } from "../../sesion";
import styles from "./UsuarioForm.module.css";

type Campo = "rol" | "profesional_id" | "activo";

const CAMPOS: readonly Campo[] = ["rol", "profesional_id", "activo"];

const IDS: Record<Campo, string> = {
  rol: "usr-editar-rol",
  profesional_id: "usr-editar-profesional",
  activo: "usr-editar-activo",
};

const OPCIONES_ROL: ReadonlyArray<{ valor: StaffRol; etiqueta: string }> = [
  { valor: "recepcion", etiqueta: "Recepción" },
  { valor: "odontologo", etiqueta: "Odontólogo" },
  { valor: "admin", etiqueta: "Admin" },
];

type Errores = Partial<Record<Campo, string>>;

function esCampo(valor: string): valor is Campo {
  return (CAMPOS as readonly string[]).includes(valor);
}

function erroresDeCampo(info: StaffErrorInfo): Errores {
  const errores: Errores = {};
  for (const [campo, mensaje] of Object.entries(info.fieldErrors)) {
    if (esCampo(campo)) {
      errores[campo] = mensaje;
    }
  }
  return errores;
}

interface EditarUsuarioFormProps {
  usuario: UsuarioStaff;
  profesionales: ProfesionalAdmin[];
  onActualizado: (usuario: UsuarioStaff) => void;
  onNoEncontrado: () => void;
  onCancelar: () => void;
}

export function EditarUsuarioForm({
  usuario,
  profesionales,
  onActualizado,
  onNoEncontrado,
  onCancelar,
}: EditarUsuarioFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [rol, setRol] = useState<StaffRol>(usuario.rol);
  const [profesionalId, setProfesionalId] = useState(
    usuario.profesional_id ?? "",
  );
  const [activo, setActivo] = useState(usuario.activo);
  const [errores, setErrores] = useState<Errores>({});
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const primero = CAMPOS.find((campo) => errores[campo] !== undefined);
    if (primero !== undefined) {
      document.getElementById(IDS[primero])?.focus();
    }
  }, [errores]);

  const cambiarRol = (nuevo: StaffRol): void => {
    setRol(nuevo);
    if (nuevo !== "odontologo") {
      setProfesionalId("");
    }
  };

  const cambios = (): UsuarioStaffUpdateInput => {
    const body: UsuarioStaffUpdateInput = {};
    if (rol !== usuario.rol) {
      body.rol = rol;
    }
    if (rol === "odontologo") {
      const elegido = profesionalId === "" ? null : profesionalId;
      if (elegido !== usuario.profesional_id) {
        body.profesional_id = elegido;
      }
    } else if (usuario.profesional_id !== null) {
      body.profesional_id = null;
    }
    if (activo !== usuario.activo) {
      body.activo = activo;
    }
    return body;
  };

  const enviar = async (body: UsuarioStaffUpdateInput): Promise<void> => {
    setEnviando(true);
    setInfo(null);
    try {
      const actualizado = await actualizarUsuarioStaff(usuario.id, body);
      onActualizado(actualizado);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "la edición del usuario staff");
      if (error.kind === "not_found") {
        onNoEncontrado();
        return;
      }
      if (error.kind === "field") {
        setErrores(erroresDeCampo(error));
      } else {
        setInfo(error);
      }
    } finally {
      setEnviando(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nuevos: Errores = {};
    if (rol === "odontologo" && profesionalId === "") {
      nuevos.profesional_id =
        "Elegí un profesional activo para el rol odontólogo.";
    }
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) {
      return;
    }
    const body = cambios();
    if (Object.keys(body).length === 0) {
      setInfo({
        kind: "unexpected",
        message: "No hay cambios para guardar.",
        fieldErrors: {},
        alternativos: [],
        codigo: null,
      });
      return;
    }
    void enviar(body);
  };

  return (
    <form
      className={styles.formulario}
      aria-label="Editar usuario staff"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h2 className={styles.titulo}>Editar usuario staff</h2>
        <button
          type="button"
          className={styles.secundario}
          disabled={enviando}
          onClick={onCancelar}
        >
          Cancelar
        </button>
      </div>

      {info !== null && (
        <p className={styles.alerta} role="alert">
          {info.message}
        </p>
      )}

      <p className={styles.lectura}>Email: {usuario.email}</p>
      <p className={styles.nota}>
        El email y la contraseña no se editan en esta pantalla.
      </p>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.rol}>
          Rol
        </label>
        <select
          className={styles.select}
          id={IDS.rol}
          name="rol"
          value={rol}
          aria-required="true"
          aria-invalid={errores.rol !== undefined}
          aria-describedby={
            errores.rol === undefined ? undefined : `${IDS.rol}-error`
          }
          onChange={(event) => cambiarRol(event.target.value as StaffRol)}
        >
          {OPCIONES_ROL.map((opcion) => (
            <option key={opcion.valor} value={opcion.valor}>
              {opcion.etiqueta}
            </option>
          ))}
        </select>
        {errores.rol !== undefined && (
          <p className={styles.error} id={`${IDS.rol}-error`} role="alert">
            {errores.rol}
          </p>
        )}
      </div>

      {rol === "odontologo" && (
        <div className={styles.campo}>
          <label className={styles.label} htmlFor={IDS.profesional_id}>
            Profesional
          </label>
          <p className={styles.ayuda}>
            Solo se ofrecen profesionales activos.
          </p>
          <select
            className={styles.select}
            id={IDS.profesional_id}
            name="profesional_id"
            value={profesionalId}
            aria-required="true"
            aria-invalid={errores.profesional_id !== undefined}
            aria-describedby={
              errores.profesional_id === undefined
                ? undefined
                : `${IDS.profesional_id}-error`
            }
            onChange={(event) => setProfesionalId(event.target.value)}
          >
            <option value="">Elegí un profesional</option>
            {profesionales.map((profesional) => (
              <option key={profesional.id} value={profesional.id}>
                {profesional.nombre}
              </option>
            ))}
          </select>
          {errores.profesional_id !== undefined && (
            <p
              className={styles.error}
              id={`${IDS.profesional_id}-error`}
              role="alert"
            >
              {errores.profesional_id}
            </p>
          )}
        </div>
      )}

      <div className={styles.campoCheck}>
        <input
          id={IDS.activo}
          name="activo"
          type="checkbox"
          checked={activo}
          onChange={(event) => setActivo(event.target.checked)}
        />
        <label className={styles.label} htmlFor={IDS.activo}>
          Activo
        </label>
      </div>

      <button className={styles.enviar} type="submit" disabled={enviando}>
        {enviando ? "Guardando." : "Guardar cambios"}
      </button>
    </form>
  );
}

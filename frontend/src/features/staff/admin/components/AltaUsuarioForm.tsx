/**
 * Alta de usuario staff (D-3): validación local alineada al contrato,
 * `profesional_id` obligatorio solo para odontólogo, selector alimentado por
 * profesionales activos y mapeo de `detail[]`/`409`/`422` accionable.
 */

import { useEffect, useState, type FormEvent } from "react";

import {
  crearUsuarioStaff,
  type ProfesionalAdmin,
  type UsuarioStaff,
} from "../../../../shared/api/admin";
import { ApiHttpError } from "../../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import type { StaffRol } from "../../../../shared/api/staff";
import { useExpirarSesion } from "../../sesion";
import styles from "./UsuarioForm.module.css";

type Campo = "email" | "password" | "rol" | "profesional_id";

const CAMPOS: readonly Campo[] = [
  "email",
  "password",
  "rol",
  "profesional_id",
];

const IDS: Record<Campo, string> = {
  email: "usr-alta-email",
  password: "usr-alta-password",
  rol: "usr-alta-rol",
  profesional_id: "usr-alta-profesional",
};

const OPCIONES_ROL: ReadonlyArray<{ valor: StaffRol; etiqueta: string }> = [
  { valor: "recepcion", etiqueta: "Recepción" },
  { valor: "odontologo", etiqueta: "Odontólogo" },
  { valor: "admin", etiqueta: "Admin" },
];

const ID_AYUDA_PROFESIONAL = "usr-alta-profesional-ayuda";

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

function emailValido(email: string): boolean {
  return /^[^@\s]+@[^@\s]+$/.test(email);
}

interface AltaUsuarioFormProps {
  profesionales: ProfesionalAdmin[];
  onCreado: (usuario: UsuarioStaff) => void;
  onCancelar: () => void;
}

export function AltaUsuarioForm({
  profesionales,
  onCreado,
  onCancelar,
}: AltaUsuarioFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState<StaffRol>("recepcion");
  const [profesionalId, setProfesionalId] = useState("");
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

  const enviar = async (): Promise<void> => {
    setEnviando(true);
    setInfo(null);
    try {
      const creado = await crearUsuarioStaff({
        email: email.trim(),
        password,
        rol,
        profesional_id: rol === "odontologo" ? profesionalId : null,
      });
      onCreado(creado);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "el alta del usuario staff");
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
    const emailLimpio = email.trim();
    if (emailLimpio === "") {
      nuevos.email = "El email es obligatorio.";
    } else if (emailLimpio.length < 3 || emailLimpio.length > 320) {
      nuevos.email = "El email debe tener entre 3 y 320 caracteres.";
    } else if (!emailValido(emailLimpio)) {
      nuevos.email = "Ingresá un email válido.";
    }
    if (password.length < 8 || password.length > 256) {
      nuevos.password = "La contraseña debe tener entre 8 y 256 caracteres.";
    }
    if (rol === "odontologo" && profesionalId === "") {
      nuevos.profesional_id =
        "Elegí un profesional activo para el rol odontólogo.";
    }
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) {
      return;
    }
    void enviar();
  };

  return (
    <form
      className={styles.formulario}
      aria-label="Alta de usuario staff"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h2 className={styles.titulo}>Alta de usuario staff</h2>
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

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.email}>
          Email
        </label>
        <input
          className={styles.input}
          id={IDS.email}
          name="email"
          type="email"
          value={email}
          autoComplete="off"
          aria-required="true"
          aria-invalid={errores.email !== undefined}
          aria-describedby={
            errores.email === undefined ? undefined : `${IDS.email}-error`
          }
          onChange={(event) => setEmail(event.target.value)}
        />
        {errores.email !== undefined && (
          <p className={styles.error} id={`${IDS.email}-error`} role="alert">
            {errores.email}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.password}>
          Contraseña
        </label>
        <input
          className={styles.input}
          id={IDS.password}
          name="password"
          type="password"
          value={password}
          autoComplete="new-password"
          aria-required="true"
          aria-invalid={errores.password !== undefined}
          aria-describedby={
            errores.password === undefined
              ? undefined
              : `${IDS.password}-error`
          }
          onChange={(event) => setPassword(event.target.value)}
        />
        {errores.password !== undefined && (
          <p
            className={styles.error}
            id={`${IDS.password}-error`}
            role="alert"
          >
            {errores.password}
          </p>
        )}
      </div>

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
          <p className={styles.ayuda} id={ID_AYUDA_PROFESIONAL}>
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
                ? ID_AYUDA_PROFESIONAL
                : `${ID_AYUDA_PROFESIONAL} ${IDS.profesional_id}-error`
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

      <button className={styles.enviar} type="submit" disabled={enviando}>
        {enviando ? "Creando." : "Crear usuario"}
      </button>
    </form>
  );
}

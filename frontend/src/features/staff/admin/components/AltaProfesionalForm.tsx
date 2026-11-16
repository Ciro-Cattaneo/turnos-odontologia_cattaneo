/**
 * Alta de profesional (D-3): validación local mínima, grilla 5–240 y mapeo
 * `detail[]` → campo con foco en el primer error y `aria-live` en la página.
 */

import { useEffect, useState, type FormEvent } from "react";

import {
  crearProfesional,
  type ProfesionalAdmin,
  type ProfesionalCreateInput,
} from "../../../../shared/api/admin";
import { ApiHttpError } from "../../../../shared/api/client";
import {
  mensajeDeError,
  type StaffErrorInfo,
} from "../../../../shared/api/errores";
import { OPCIONES_DURACION_PROFESIONAL, esDuracionProfesionalValida } from "../duraciones";
import { useExpirarSesion } from "../../sesion";
import styles from "./ProfesionalForm.module.css";

type Campo = "nombre" | "matricula" | "especialidad" | "duracion_default_min";

const CAMPOS: readonly Campo[] = [
  "nombre",
  "matricula",
  "especialidad",
  "duracion_default_min",
];

const IDS: Record<Campo, string> = {
  nombre: "prof-alta-nombre",
  matricula: "prof-alta-matricula",
  especialidad: "prof-alta-especialidad",
  duracion_default_min: "prof-alta-duracion",
};

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

interface AltaProfesionalFormProps {
  onCreado: (profesional: ProfesionalAdmin) => void;
  onCancelar: () => void;
}

export function AltaProfesionalForm({
  onCreado,
  onCancelar,
}: AltaProfesionalFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [nombre, setNombre] = useState("");
  const [matricula, setMatricula] = useState("");
  const [especialidad, setEspecialidad] = useState("");
  const [duracion, setDuracion] = useState(30);
  const [errores, setErrores] = useState<Errores>({});
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const primero = CAMPOS.find((campo) => errores[campo] !== undefined);
    if (primero !== undefined) {
      document.getElementById(IDS[primero])?.focus();
    }
  }, [errores]);

  const enviar = async (body: ProfesionalCreateInput): Promise<void> => {
    setEnviando(true);
    setInfo(null);
    try {
      const creado = await crearProfesional(body);
      onCreado(creado);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "el alta del profesional");
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
    if (nombre.trim() === "") {
      nuevos.nombre = "El nombre es obligatorio.";
    }
    if (!esDuracionProfesionalValida(duracion)) {
      nuevos.duracion_default_min =
        "La duración debe ser un múltiplo de 5 entre 5 y 240.";
    }
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) {
      return;
    }
    void enviar({
      nombre: nombre.trim(),
      matricula: matricula.trim() === "" ? null : matricula.trim(),
      especialidad:
        especialidad.trim() === "" ? null : especialidad.trim(),
      duracion_default_min: duracion,
    });
  };

  return (
    <form
      className={styles.formulario}
      aria-label="Alta de profesional"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h2 className={styles.titulo}>Alta de profesional</h2>
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
        <label className={styles.label} htmlFor={IDS.nombre}>
          Nombre
        </label>
        <input
          className={styles.input}
          id={IDS.nombre}
          name="nombre"
          type="text"
          value={nombre}
          autoComplete="off"
          aria-required="true"
          aria-invalid={errores.nombre !== undefined}
          aria-describedby={
            errores.nombre === undefined
              ? undefined
              : `${IDS.nombre}-error`
          }
          onChange={(event) => setNombre(event.target.value)}
        />
        {errores.nombre !== undefined && (
          <p className={styles.error} id={`${IDS.nombre}-error`} role="alert">
            {errores.nombre}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.matricula}>
          Matrícula
        </label>
        <input
          className={styles.input}
          id={IDS.matricula}
          name="matricula"
          type="text"
          value={matricula}
          autoComplete="off"
          aria-invalid={errores.matricula !== undefined}
          aria-describedby={
            errores.matricula === undefined
              ? undefined
              : `${IDS.matricula}-error`
          }
          onChange={(event) => setMatricula(event.target.value)}
        />
        {errores.matricula !== undefined && (
          <p
            className={styles.error}
            id={`${IDS.matricula}-error`}
            role="alert"
          >
            {errores.matricula}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.especialidad}>
          Especialidad
        </label>
        <input
          className={styles.input}
          id={IDS.especialidad}
          name="especialidad"
          type="text"
          value={especialidad}
          autoComplete="off"
          aria-invalid={errores.especialidad !== undefined}
          aria-describedby={
            errores.especialidad === undefined
              ? undefined
              : `${IDS.especialidad}-error`
          }
          onChange={(event) => setEspecialidad(event.target.value)}
        />
        {errores.especialidad !== undefined && (
          <p
            className={styles.error}
            id={`${IDS.especialidad}-error`}
            role="alert"
          >
            {errores.especialidad}
          </p>
        )}
      </div>

      <div className={styles.campo}>
        <label className={styles.label} htmlFor={IDS.duracion_default_min}>
          Duración
        </label>
        <select
          className={styles.select}
          id={IDS.duracion_default_min}
          name="duracion_default_min"
          value={duracion}
          aria-required="true"
          aria-invalid={errores.duracion_default_min !== undefined}
          aria-describedby={
            errores.duracion_default_min === undefined
              ? undefined
              : `${IDS.duracion_default_min}-error`
          }
          onChange={(event) => setDuracion(Number(event.target.value))}
        >
          {OPCIONES_DURACION_PROFESIONAL.map((opcion) => (
            <option key={opcion} value={opcion}>
              {opcion} min
            </option>
          ))}
        </select>
        {errores.duracion_default_min !== undefined && (
          <p
            className={styles.error}
            id={`${IDS.duracion_default_min}-error`}
            role="alert"
          >
            {errores.duracion_default_min}
          </p>
        )}
      </div>

      <button className={styles.enviar} type="submit" disabled={enviando}>
        {enviando ? "Creando." : "Crear profesional"}
      </button>
    </form>
  );
}

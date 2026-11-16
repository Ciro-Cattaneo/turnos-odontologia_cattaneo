/**
 * Edición de profesional (D-3): envía solo los campos modificados, permite
 * cambiar `activo`, mapea `detail[]` a cada campo y trata el 404 cerrando el
 * formulario con refresco del listado.
 */

import { useEffect, useState, type FormEvent } from "react";

import {
  actualizarProfesional,
  type ProfesionalAdmin,
  type ProfesionalUpdateInput,
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
  nombre: "prof-editar-nombre",
  matricula: "prof-editar-matricula",
  especialidad: "prof-editar-especialidad",
  duracion_default_min: "prof-editar-duracion",
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

function textoOpcional(valor: string): string | null {
  return valor.trim() === "" ? null : valor.trim();
}

interface EditarProfesionalFormProps {
  profesional: ProfesionalAdmin;
  onActualizado: (profesional: ProfesionalAdmin) => void;
  onNoEncontrado: () => void;
  onCancelar: () => void;
}

export function EditarProfesionalForm({
  profesional,
  onActualizado,
  onNoEncontrado,
  onCancelar,
}: EditarProfesionalFormProps): JSX.Element {
  const expirarSesion = useExpirarSesion();
  const [nombre, setNombre] = useState(profesional.nombre);
  const [matricula, setMatricula] = useState(profesional.matricula ?? "");
  const [especialidad, setEspecialidad] = useState(
    profesional.especialidad ?? "",
  );
  const [duracion, setDuracion] = useState(profesional.duracion_default_min);
  const [activo, setActivo] = useState(profesional.activo);
  const [errores, setErrores] = useState<Errores>({});
  const [info, setInfo] = useState<StaffErrorInfo | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const primero = CAMPOS.find((campo) => errores[campo] !== undefined);
    if (primero !== undefined) {
      document.getElementById(IDS[primero])?.focus();
    }
  }, [errores]);

  const cambios = (): ProfesionalUpdateInput => {
    const body: ProfesionalUpdateInput = {};
    const nombreLimpio = nombre.trim();
    if (nombreLimpio !== profesional.nombre) {
      body.nombre = nombreLimpio;
    }
    const matriculaLimpia = textoOpcional(matricula);
    if (matriculaLimpia !== profesional.matricula) {
      body.matricula = matriculaLimpia;
    }
    const especialidadLimpia = textoOpcional(especialidad);
    if (especialidadLimpia !== profesional.especialidad) {
      body.especialidad = especialidadLimpia;
    }
    if (duracion !== profesional.duracion_default_min) {
      body.duracion_default_min = duracion;
    }
    if (activo !== profesional.activo) {
      body.activo = activo;
    }
    return body;
  };

  const enviar = async (body: ProfesionalUpdateInput): Promise<void> => {
    setEnviando(true);
    setInfo(null);
    try {
      const actualizado = await actualizarProfesional(profesional.id, body);
      onActualizado(actualizado);
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        expirarSesion();
        return;
      }
      const error = mensajeDeError(err, "la edición del profesional");
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
      aria-label="Editar profesional"
      noValidate
      onSubmit={handleSubmit}
    >
      <div className={styles.encabezado}>
        <h2 className={styles.titulo}>Editar profesional</h2>
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

      <div className={styles.campoCheck}>
        <input
          id="prof-editar-activo"
          name="activo"
          type="checkbox"
          checked={activo}
          onChange={(event) => setActivo(event.target.checked)}
        />
        <label className={styles.label} htmlFor="prof-editar-activo">
          Activo
        </label>
      </div>

      <button className={styles.enviar} type="submit" disabled={enviando}>
        {enviando ? "Guardando." : "Guardar cambios"}
      </button>
    </form>
  );
}

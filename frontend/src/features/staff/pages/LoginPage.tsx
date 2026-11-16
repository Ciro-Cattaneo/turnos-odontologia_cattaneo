/**
 * Login staff por cookie httpOnly: `400` por campo, `401` genérico y `429`
 * con la espera de `Retry-After` (D-3, D-13).
 */

import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiHttpError } from "../../../shared/api/client";
import { mensajeDeError } from "../../../shared/api/errores";
import { login } from "../../../shared/api/staff";
import { CampoTexto } from "../../reserva/components/CampoTexto";
import { AVISO_SESION_EXPIRADA, avisoDeEstado } from "../sesion";
import styles from "./LoginPage.module.css";

const MENSAJE_CREDENCIALES =
  "Credenciales inválidas. Revisá tu email y tu contraseña.";

interface ErroresCampo {
  email?: string;
  password?: string;
}

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const aviso = avisoDeEstado(location.state);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erroresCampo, setErroresCampo] = useState<ErroresCampo>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (erroresCampo.email !== undefined) {
      document.getElementById("email")?.focus();
    } else if (erroresCampo.password !== undefined) {
      document.getElementById("password")?.focus();
    }
  }, [erroresCampo]);

  const enviar = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (enviando) {
      return;
    }
    setEnviando(true);
    setErrorGeneral(null);
    setErroresCampo({});
    try {
      await login({ email, password });
      navigate("/staff/agenda", { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 401) {
        setErrorGeneral(MENSAJE_CREDENCIALES);
      } else if (err instanceof ApiHttpError && err.status === 400) {
        const info = mensajeDeError(err, "el inicio de sesión");
        const campos: ErroresCampo = {};
        if (info.fieldErrors["email"] !== undefined) {
          campos.email = info.fieldErrors["email"];
        }
        if (info.fieldErrors["password"] !== undefined) {
          campos.password = info.fieldErrors["password"];
        }
        setErroresCampo(campos);
        setErrorGeneral(
          Object.keys(campos).length > 0 ? info.message : "Revisá los datos ingresados.",
        );
      } else {
        setErrorGeneral(mensajeDeError(err, "el inicio de sesión").message);
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className={styles.pagina}>
      <h1 className={styles.titulo}>Iniciar sesión</h1>

      {aviso === "sesion_expirada" && (
        <p className={styles.alerta} role="alert">
          {AVISO_SESION_EXPIRADA}
        </p>
      )}

      <form
        className={styles.formulario}
        noValidate
        onSubmit={(event) => {
          void enviar(event);
        }}
      >
        <CampoTexto
          id="email"
          label="Email"
          type="email"
          value={email}
          autoComplete="username"
          inputMode="email"
          onChange={setEmail}
          error={erroresCampo.email}
        />
        <CampoTexto
          id="password"
          label="Contraseña"
          type="password"
          value={password}
          autoComplete="current-password"
          onChange={setPassword}
          error={erroresCampo.password}
        />

        {errorGeneral !== null && (
          <p className={styles.alerta} role="alert">
            {errorGeneral}
          </p>
        )}

        <button type="submit" className={styles.boton} disabled={enviando}>
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </main>
  );
}

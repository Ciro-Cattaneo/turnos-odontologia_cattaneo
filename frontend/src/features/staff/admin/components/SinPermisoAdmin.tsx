/** Falta de permiso genérica de las pantallas admin (D-9). */

import styles from "./SinPermisoAdmin.module.css";

export function SinPermisoAdmin(): JSX.Element {
  return (
    <p className={styles.alerta} role="alert">
      No tenés permiso para esta acción.
    </p>
  );
}

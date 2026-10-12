import { Link } from "react-router-dom";

export function NotFound(): JSX.Element {
  return (
    <main className="shell">
      <h1>Página no encontrada</h1>
      <p>La dirección que buscás no existe o fue movida.</p>
      <Link className="action" to="/">
        Volver al inicio
      </Link>
    </main>
  );
}

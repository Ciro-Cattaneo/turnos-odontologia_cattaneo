import { Link } from "react-router-dom";

export function Home(): JSX.Element {
  return (
    <main className="shell">
      <h1>Turnos Odontología Cattaneo</h1>
      <p>Reservá tu turno online: elegí profesional, día y horario.</p>
      <Link className="action" to="/reservar">
        Reservar turno
      </Link>
    </main>
  );
}

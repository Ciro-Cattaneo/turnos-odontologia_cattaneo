/** Resumen del 201, link y estado de notificaciones (capa: unit/componente, R5). */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { TurnoOut } from "../../../shared/api/reserva";
import { ReservaResumen } from "../components/ReservaResumen";

const turno: TurnoOut = {
  id: "22222222-2222-4222-8222-222222222222",
  estado: "reservado",
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
  profesional: {
    id: "11111111-1111-4111-8111-111111111111",
    nombre: "Dra. Ficticia Test",
  },
  paciente: {
    nombre: "Paciente Ficticio Test",
    dni: "30000001",
    email: "paciente@ejemplo.test",
  },
  token_cancelacion: "33333333-3333-4333-8333-333333333333",
  cancel_url:
    "/cancelar?token=33333333-3333-4333-8333-333333333333&id=22222222-2222-4222-8222-222222222222",
  notificaciones_encoladas: true,
};

afterEach(cleanup);

describe("ReservaResumen", () => {
  it("test_resumen_201_muestra_turno_y_link", () => {
    render(<ReservaResumen turno={turno} />);

    expect(screen.getByText("Dra. Ficticia Test")).toBeDefined();
    expect(screen.getByText("10/11/2026")).toBeDefined();
    expect(screen.getByText("09:00–09:30")).toBeDefined();
    expect(screen.getByText("30 min")).toBeDefined();
    expect(screen.getByText("reservado")).toBeDefined();

    const link = screen.getByRole("link", { name: /cancelar turno/i });
    expect(link.getAttribute("href")).toBe(
      "/cancelar?token=33333333-3333-4333-8333-333333333333&id=22222222-2222-4222-8222-222222222222",
    );
  });

  it.each([true, false])(
    "test_resumen_201_notificaciones_encoladas_parametrizado (%s)",
    (encoladas) => {
      render(
        <ReservaResumen
          turno={{ ...turno, notificaciones_encoladas: encoladas }}
        />,
      );

      if (encoladas) {
        expect(screen.getByText(/se enviarán por mail/i)).toBeDefined();
        expect(screen.queryByText(/no se pudieron encolar/i)).toBeNull();
      } else {
        expect(
          screen.getByText(/no se pudieron encolar los mails/i),
        ).toBeDefined();
        expect(screen.getByText(/contactá al consultorio/i)).toBeDefined();
      }
      expect(screen.queryByText(/sin mail/i)).toBeNull();
    },
  );
});

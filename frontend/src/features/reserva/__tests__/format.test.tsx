/**
 * Formateo siempre en America/Argentina/Buenos_Aires (capa: unit/componente, R15).
 * Se usan instantes UTC que caen en otro día calendario de Buenos Aires para
 * probar que la zona del consultorio se impone a la del host.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Slot } from "../../../shared/api/client";
import type { TurnoOut } from "../../../shared/api/reserva";
import { ReservaResumen } from "../components/ReservaResumen";
import { SlotList } from "../components/SlotList";

const slotUtc: Slot = {
  inicio: "2026-11-11T02:00:00Z",
  fin: "2026-11-11T02:30:00Z",
  duracion_min: 30,
};

const turnoUtc: TurnoOut = {
  id: "22222222-2222-4222-8222-222222222222",
  estado: "reservado",
  inicio: "2026-11-11T02:00:00Z",
  fin: "2026-11-11T02:30:00Z",
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

describe("formateo en zona Buenos Aires", () => {
  it("test_slots_y_resumen_se_formatean_en_zona_buenos_aires", () => {
    const { unmount } = render(
      <SlotList slots={[slotUtc]} onSelect={() => undefined} />,
    );
    expect(
      screen.getByRole("button", { name: "23:00 a 23:30, 30 min" }),
    ).toBeDefined();
    unmount();

    render(<ReservaResumen turno={turnoUtc} />);
    const resumen = screen.getByRole("region", { name: /resumen de la reserva/i });
    expect(within(resumen).getByText("10/11/2026")).toBeDefined();
    expect(within(resumen).getByText("23:00–23:30")).toBeDefined();
  });
});

/** Alternativos del 409 y conservación de datos (capa: unit/componente, R6). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { Slot } from "../../../shared/api/client";
import { AlternativosList } from "../components/AlternativosList";
import { ReservaForm } from "../components/ReservaForm";

const original: Slot = {
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
};

const alternativos: Slot[] = [
  {
    inicio: "2026-11-10T09:30:00-03:00",
    fin: "2026-11-10T10:00:00-03:00",
    duracion_min: 30,
  },
  {
    inicio: "2026-11-10T11:00:00-03:00",
    fin: "2026-11-10T11:30:00-03:00",
    duracion_min: 30,
  },
];

function Harness(): JSX.Element {
  const [slot, setSlot] = useState<Slot>(original);
  const [lista, setLista] = useState<Slot[]>(alternativos);
  return (
    <div>
      <ReservaForm slot={slot} submitting={false} onSubmit={() => undefined} />
      {lista.length > 0 && (
        <AlternativosList
          alternativos={lista}
          onSelect={(nuevo) => {
            setSlot(nuevo);
            setLista([]);
          }}
        />
      )}
    </div>
  );
}

afterEach(cleanup);

describe("AlternativosList", () => {
  it("test_409_muestra_alternativos_y_conserva_datos", () => {
    render(<Harness />);

    fireEvent.change(screen.getByLabelText("Nombre y apellido"), {
      target: { value: "Paciente Ficticio Test" },
    });

    expect(
      screen.getByRole("button", { name: "09:30 a 10:00" }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: "11:00 a 11:30" }),
    ).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "09:30 a 10:00" }));

    expect(screen.getByText(/09:30–10:00/)).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe("Paciente Ficticio Test");
    expect(screen.queryByText(/reserva confirmada/i)).toBeNull();
    expect(
      screen.queryByRole("button", { name: "11:00 a 11:30" }),
    ).toBeNull();
  });

  it("test_409_sin_alternativos_invita_a_otra_fecha", () => {
    render(<AlternativosList alternativos={[]} onSelect={() => undefined} />);

    expect(screen.getByText(/probá con otra fecha/i)).toBeDefined();
  });
});

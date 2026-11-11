/** Lista de slots y apertura del formulario (capa: unit/componente, R3). */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { Slot } from "../../../shared/api/client";
import { ReservaForm } from "../components/ReservaForm";
import { SlotList } from "../components/SlotList";

const slots: Slot[] = [
  {
    inicio: "2026-11-10T09:00:00-03:00",
    fin: "2026-11-10T09:30:00-03:00",
    duracion_min: 30,
  },
  {
    inicio: "2026-11-10T10:00:00-03:00",
    fin: "2026-11-10T10:45:00-03:00",
    duracion_min: 45,
  },
];

function SelectorHarness(): JSX.Element {
  const [slot, setSlot] = useState<Slot | null>(null);
  return (
    <div>
      <SlotList slots={slots} onSelect={setSlot} />
      {slot !== null && (
        <ReservaForm slot={slot} submitting={false} onSubmit={() => undefined} />
      )}
    </div>
  );
}

afterEach(cleanup);

describe("SlotList", () => {
  it("test_slots_muestra_solo_libres_con_inicio_fin_duracion", () => {
    render(<SlotList slots={slots} onSelect={() => undefined} />);

    const botones = screen.getAllByRole("button");
    expect(botones).toHaveLength(slots.length);
    expect(
      screen.getByRole("button", { name: "09:00 a 09:30, 30 min" }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: "10:00 a 10:45, 45 min" }),
    ).toBeDefined();
  });

  it("test_seleccionar_slot_habilita_formulario", () => {
    render(<SelectorHarness />);

    expect(screen.queryByRole("form")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "09:00 a 09:30, 30 min" }));

    const form = screen.getByRole("form");
    expect(within(form).getByText(/horario elegido/i)).toBeDefined();
    expect(within(form).getByText(/09:00–09:30/)).toBeDefined();
  });
});

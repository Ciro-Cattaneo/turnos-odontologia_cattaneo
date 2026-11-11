/** Selector de profesionales (capa: unit/componente, R2 S1-S2). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Profesional } from "../../../shared/api/reserva";
import { ProfesionalSelector } from "../components/ProfesionalSelector";

const profesionales: Profesional[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    nombre: "Dra. Ficticia Test",
    especialidad: "Odontología",
    matricula: "MP-0000",
    duracion_default_min: 30,
    ultima_actualizacion: null,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    nombre: "Dr. Ficticio Test",
    especialidad: null,
    matricula: null,
    duracion_default_min: 45,
    ultima_actualizacion: "2026-11-09T10:00:00+00:00",
  },
];

afterEach(cleanup);

describe("ProfesionalSelector", () => {
  it("test_selector_profesionales_lista_solo_activos", () => {
    const onChange = vi.fn();
    render(
      <ProfesionalSelector
        profesionales={profesionales}
        value=""
        onChange={onChange}
      />,
    );

    expect(
      screen.getByRole("option", { name: /Dra\. Ficticia Test/ }),
    ).toBeDefined();
    expect(
      screen.getByRole("option", { name: /Dr\. Ficticio Test/ }),
    ).toBeDefined();

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: profesionales[0]?.id ?? "" },
    });
    expect(onChange).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111");
  });

  it("test_profesionales_vacio_muestra_mensaje_sin_formulario", () => {
    render(
      <ProfesionalSelector profesionales={[]} value="" onChange={vi.fn()} />,
    );

    expect(screen.getByText(/no hay profesionales disponibles/i)).toBeDefined();
    expect(screen.queryByRole("form")).toBeNull();
    expect(screen.queryByLabelText("Fecha")).toBeNull();
  });
});

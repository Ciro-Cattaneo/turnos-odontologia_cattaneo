/** Formulario de reserva: validación local y mapeo del 400 (capa: unit/componente, R4). */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiErrorDetail, Slot } from "../../../shared/api/client";
import { ReservaForm } from "../components/ReservaForm";
import type { FormValues } from "../types";

const slot: Slot = {
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
};

const valoresValidos: FormValues = {
  nombre: "Paciente Ficticio Test",
  dni: "30000001",
  telefono: "1100000001",
  obra_social: "Obra Social Test",
  email: "paciente@ejemplo.test",
};

function completarFormulario(valores: FormValues): void {
  fireEvent.change(screen.getByLabelText("Nombre y apellido"), {
    target: { value: valores.nombre },
  });
  fireEvent.change(screen.getByLabelText("DNI"), {
    target: { value: valores.dni },
  });
  fireEvent.change(screen.getByLabelText("Teléfono"), {
    target: { value: valores.telefono },
  });
  fireEvent.change(screen.getByLabelText("Obra social"), {
    target: { value: valores.obra_social },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: valores.email },
  });
}

afterEach(cleanup);

describe("ReservaForm", () => {
  it("test_formulario_campos_faltantes_no_envia", () => {
    const onSubmit = vi.fn();
    render(
      <ReservaForm slot={slot} submitting={false} onSubmit={onSubmit} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    for (const etiqueta of [
      "Nombre y apellido",
      "DNI",
      "Teléfono",
      "Obra social",
      "Email",
    ]) {
      const input = screen.getByLabelText(etiqueta);
      expect(input.getAttribute("aria-invalid")).toBe("true");
      expect(input.getAttribute("aria-describedby")).not.toBeNull();
    }
    expect(screen.getAllByRole("alert").length).toBeGreaterThanOrEqual(5);
  });

  it("test_formulario_mail_invalido_marca_solo_email", () => {
    const onSubmit = vi.fn();
    render(
      <ReservaForm slot={slot} submitting={false} onSubmit={onSubmit} />,
    );

    completarFormulario({ ...valoresValidos, email: "no-es-email" });
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe(
      "true",
    );
    for (const etiqueta of ["Nombre y apellido", "DNI", "Teléfono", "Obra social"]) {
      expect(screen.getByLabelText(etiqueta).getAttribute("aria-invalid")).toBe(
        "false",
      );
    }
    expect(screen.queryByText(/ingresá tu nombre/i)).toBeNull();
    expect(screen.getByText(/email válido/i)).toBeDefined();
  });

  it("test_formulario_400_marca_campos_y_conserva_valores", () => {
    const detalle: ApiErrorDetail = [
      {
        campo: "paciente.email",
        error: "El mail fue rechazado",
        tipo: "value_error",
      },
    ];
    render(
      <ReservaForm
        slot={slot}
        submitting={false}
        initialValues={valoresValidos}
        serverDetail={detalle}
        onSubmit={vi.fn()}
      />,
    );

    const email = screen.getByLabelText("Email") as HTMLInputElement;
    expect(email.value).toBe(valoresValidos.email);
    expect(email.getAttribute("aria-invalid")).toBe("true");
    expect(email.getAttribute("aria-describedby")).toBe("email-error");
    expect(screen.getByText("El mail fue rechazado")).toBeDefined();
  });

  it.each(["inicio", "duracion_min"])(
    "test_formulario_400_inicio_duracion_es_error_slot (%s)",
    (campo) => {
      const detalle: ApiErrorDetail = [
        { campo, error: "Horario inválido", tipo: "value_error" },
      ];
      render(
        <ReservaForm
          slot={slot}
          submitting={false}
          initialValues={valoresValidos}
          serverDetail={detalle}
          onSubmit={vi.fn()}
        />,
      );

      const form = screen.getByRole("form");
      expect(
        within(form).getByText(/volvé a consultar la disponibilidad/i),
      ).toBeDefined();
      expect(
        (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
      ).toBe(valoresValidos.nombre);
      expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
        valoresValidos.email,
      );
    },
  );

  it("test_formulario_400_no_muestra_resumen", () => {
    const detalle: ApiErrorDetail = [
      { campo: "paciente.dni", error: "DNI inválido", tipo: "value_error" },
    ];
    render(
      <ReservaForm
        slot={slot}
        submitting={false}
        initialValues={valoresValidos}
        serverDetail={detalle}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByText(/reserva confirmada/i)).toBeNull();
    expect(screen.getByRole("form")).toBeDefined();
  });

  it("test_formulario_campos_con_etiqueta", () => {
    render(<ReservaForm slot={slot} submitting={false} onSubmit={vi.fn()} />);

    const campos: Array<[string, string]> = [
      ["nombre", "Nombre y apellido"],
      ["dni", "DNI"],
      ["telefono", "Teléfono"],
      ["obra_social", "Obra social"],
      ["email", "Email"],
    ];
    for (const [id, etiqueta] of campos) {
      const input = screen.getByLabelText(etiqueta) as HTMLInputElement;
      expect(input.id).toBe(id);
      expect(input.getAttribute("aria-required")).toBe("true");
      const label = screen.getByText(etiqueta);
      expect(label.tagName).toBe("LABEL");
      expect(label.getAttribute("for")).toBe(id);
    }
  });

  it("test_formulario_errores_anunciados", () => {
    render(<ReservaForm slot={slot} submitting={false} onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    const campos = ["nombre", "dni", "telefono", "obra_social", "email"];
    for (const id of campos) {
      const input = document.getElementById(id) as HTMLInputElement;
      expect(input.getAttribute("aria-invalid")).toBe("true");
      const errorId = input.getAttribute("aria-describedby");
      expect(errorId).toBe(`${id}-error`);
      const error = document.getElementById(`${id}-error`);
      expect(error).not.toBeNull();
      expect(error?.getAttribute("role")).toBe("alert");
    }
    expect(screen.getAllByRole("alert")).toHaveLength(campos.length);
  });

  it("test_formulario_orden_dom_y_aria", () => {
    // La verificación manual de `:focus-visible` queda fuera del test: no se
    // instala `user-event`; se revisa en navegador con Tab.
    render(<ReservaForm slot={slot} submitting={false} onSubmit={vi.fn()} />);

    const form = screen.getByRole("form", { name: "Formulario de reserva" });
    expect(form.tagName).toBe("FORM");

    const orden = screen
      .getAllByRole("textbox")
      .map((input) => input.getAttribute("id"));
    expect(orden).toEqual(["nombre", "dni", "telefono", "obra_social", "email"]);

    const leyenda = screen.getByText("Datos del paciente");
    expect(leyenda.tagName).toBe("LEGEND");
    expect(
      leyenda.compareDocumentPosition(document.getElementById("nombre") ?? leyenda) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const enviar = screen.getByRole("button", { name: /confirmar reserva/i });
    const email = screen.getByLabelText("Email");
    expect(
      email.compareDocumentPosition(enviar) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});

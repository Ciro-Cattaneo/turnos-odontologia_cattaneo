/**
 * Layout staff protegido (capa: integración, router en memoria, fetch de borde).
 * # AC frontend-agenda-staff/Sesión staff — bootstrap de sesión y reintento
 * ante error de red (triangulación del 401 y del 200 ya cubiertos en sesion).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const profesionalesVacios = { items: [], next_cursor: null };

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp(initial: string): void {
  const router = createMemoryRouter(appRoutes, { initialEntries: [initial] });
  render(<RouterProvider router={router} />);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("layout staff", () => {
  it("test_error_de_red_al_resolver_sesion_permite_reintentar", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    renderApp("/staff/agenda");

    expect(await screen.findByText(/no pudimos conectarnos/i)).toBeDefined();
    expect(screen.queryByRole("heading", { name: /iniciar sesión/i })).toBeNull();

    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(
      await screen.findByRole("heading", { name: /^agenda$/i }),
    ).toBeDefined();
    expect(screen.getByText("recepcion@ficticio.test")).toBeDefined();
  });
});

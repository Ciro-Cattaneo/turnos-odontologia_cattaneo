/**
 * Sesión staff: bootstrap con `/api/auth/me`, protección de rutas y expiración
 * durante una operación (capa: integración, router en memoria, fetch de borde).
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
const meOdontologo = {
  email: "odontologo@ficticio.test",
  rol: "odontologo",
  profesional_id: "11111111-1111-4111-8111-111111111111",
};
const profesionalesVacios = { items: [], next_cursor: null };

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp(initial: string): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, { initialEntries: [initial] });
  render(<RouterProvider router={router} />);
  return router;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sesión staff", () => {
  it("test_sin_sesion_redirige_a_login_sin_renderizar_agenda", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json({ detail: "No autenticado" }, 401));

    renderApp("/staff/agenda");

    expect(
      await screen.findByRole("heading", { name: /iniciar sesión/i }),
    ).toBeDefined();
    expect(screen.queryByRole("heading", { name: /^agenda$/i })).toBeNull();
  });

  it("test_con_sesion_renderiza_outlet_y_sesion_acotada", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));

    renderApp("/staff/agenda");

    expect(
      await screen.findByRole("heading", { name: /^agenda$/i }),
    ).toBeDefined();
    expect(screen.getByText("recepcion@ficticio.test")).toBeDefined();
    expect(
      screen.getByRole("link", { name: /notificaciones fallidas/i }),
    ).toBeDefined();
  });

  it("test_odontologo_no_ve_entrada_de_notificaciones", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meOdontologo));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));

    renderApp("/staff/agenda");

    expect(
      await screen.findByRole("heading", { name: /mi agenda/i }),
    ).toBeDefined();
    expect(
      screen.queryByRole("link", { name: /notificaciones fallidas/i }),
    ).toBeNull();
  });

  it("test_sesion_expirada_al_refrescar_limpia_estado_y_redirige", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));
    fetchMock.mockResolvedValueOnce(json({ detail: "No autenticado" }, 401));

    renderApp("/staff/agenda");

    await screen.findByRole("heading", { name: /^agenda$/i });
    expect(await screen.findByText(/profesionales: 0/i)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: /actualizar/i }));

    expect(
      await screen.findByRole("heading", { name: /iniciar sesión/i }),
    ).toBeDefined();
    expect(screen.getByText(/sesión expiró/i)).toBeDefined();
    expect(screen.queryByText("recepcion@ficticio.test")).toBeNull();
  });
});

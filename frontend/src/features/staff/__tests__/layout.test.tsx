/**
 * Layout staff protegido (capa: integración, router en memoria, fetch de borde).
 * # AC frontend-agenda-staff/Sesión staff — bootstrap de sesión y reintento
 * ante error de red (triangulación del 401 y del 200 ya cubiertos en sesion).
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const meAdmin = {
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
};
const meOdontologo = {
  email: "odontologo@cattaneo.test",
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

function renderApp(initial: string): void {
  const router = createMemoryRouter(appRoutes, { initialEntries: [initial] });
  render(<RouterProvider router={router} />);
}

function enlacesDeNav(): string[] {
  const nav = screen.getByRole("navigation", { name: /navegación staff/i });
  return within(nav)
    .getAllByRole("link")
    .map((enlace) => (enlace.textContent ?? "").trim());
}

async function enlacesConSesion(sesion: { email: string }): Promise<string[]> {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock
    .mockResolvedValueOnce(json(sesion))
    .mockResolvedValueOnce(json(profesionalesVacios));
  renderApp("/staff/agenda");
  await screen.findByText(sesion.email);
  return enlacesDeNav();
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("layout staff", () => {
  it.each([
    ["admin", meAdmin, 3],
    ["recepcion", meRecepcion, 0],
    ["odontologo", meOdontologo, 0],
  ])(
    "test_nav_admin_visible_solo_para_%s",
    async (_rol, sesion, cantidad) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      fetchMock
        .mockResolvedValueOnce(json(sesion))
        .mockResolvedValueOnce(json(profesionalesVacios));

      renderApp("/staff/agenda");
      await screen.findByText(sesion.email);

      const enlaces = [
        screen.queryByRole("link", { name: /profesionales/i }),
        screen.queryByRole("link", { name: /usuarios staff/i }),
        screen.queryByRole("link", { name: /reportes/i }),
      ].filter((enlace) => enlace !== null);

      expect(enlaces).toHaveLength(cantidad);
    },
  );

  it("test_nav_staff_existente_no_se_reordena_ni_duplica", async () => {
    const admin = await enlacesConSesion(meAdmin);
    expect(admin).toEqual([
      "Agenda",
      "Notificaciones fallidas",
      "Profesionales",
      "Usuarios staff",
      "Reportes",
    ]);
    expect(new Set(admin).size).toBe(admin.length);

    cleanup();
    vi.unstubAllGlobals();

    const recepcion = await enlacesConSesion(meRecepcion);
    expect(recepcion).toEqual(["Agenda", "Notificaciones fallidas"]);

    cleanup();
    vi.unstubAllGlobals();

    const odontologo = await enlacesConSesion(meOdontologo);
    expect(odontologo).toEqual(["Agenda"]);
  });

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

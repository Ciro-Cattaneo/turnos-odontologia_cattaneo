/**
 * Rutas staff y no-regresión pública (capa: integración, router en memoria).
 * # AC frontend-shell/S1/S2/S5 (delta C-10) — login fuera del layout, agenda y
 * notificaciones dentro, públicas sin sesión.
 */

import { render, screen } from "@testing-library/react";
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
const meAdmin = {
  email: "admin@cattaneo.test",
  rol: "admin",
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

describe("rutas staff", () => {
  it("test_login_no_resuelve_sesion_ni_muestra_navegacion_protegida", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/staff/login");

    expect(
      screen.getByRole("heading", { name: /iniciar sesión/i }),
    ).toBeDefined();
    expect(
      screen.queryByRole("link", { name: /notificaciones fallidas/i }),
    ).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("test_agenda_con_sesion_resuelve_dentro_del_layout", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));

    renderApp("/staff/agenda");

    expect(
      await screen.findByRole("heading", { name: /^agenda$/i }),
    ).toBeDefined();
    expect(
      screen.getByRole("link", { name: /notificaciones fallidas/i }),
    ).toBeDefined();
  });

  it("test_notificaciones_con_recepcion_renderiza_el_panel", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValueOnce(json(meRecepcion));

    renderApp("/staff/notificaciones");

    expect(
      await screen.findByRole("heading", { name: /notificaciones fallidas/i }),
    ).toBeDefined();
  });

  it("test_notificaciones_con_odontologo_muestra_403_generico", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValueOnce(json(meOdontologo));

    renderApp("/staff/notificaciones");

    expect(
      await screen.findByText(/no tenés permiso para esta acción/i),
    ).toBeDefined();
  });

  it.each([
    ["/staff/admin/profesionales", /^profesionales$/i],
    ["/staff/admin/usuarios", /^usuarios staff$/i],
    ["/staff/admin/reportes", /^reportes$/i],
  ])(
    "test_ruta_admin_%s_con_admin_resuelve_en_layout",
    async (ruta, encabezado) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      fetchMock
        .mockResolvedValueOnce(json(meAdmin))
        .mockResolvedValue(json(profesionalesVacios));

      renderApp(ruta);

      expect(
        await screen.findByRole("heading", { name: encabezado }),
      ).toBeDefined();
      expect(screen.getByRole("link", { name: /agenda/i })).toBeDefined();
      expect(screen.queryByText(/no tenés permiso/i)).toBeNull();
    },
  );

  it.each([
    ["recepcion", meRecepcion],
    ["odontologo", meOdontologo],
  ])(
    "test_acceso_directo_admin_con_%s_muestra_403_sin_romper_layout",
    async (_rol, sesion) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      fetchMock.mockResolvedValue(json(sesion));

      renderApp("/staff/admin/profesionales");

      expect(
        await screen.findByText(/no tenés permiso para esta acción/i),
      ).toBeDefined();
      expect(screen.queryByText(/página no encontrada/i)).toBeNull();
      expect(screen.getByRole("link", { name: /agenda/i })).toBeDefined();
      const urls = fetchMock.mock.calls.map((llamada) => String(llamada[0]));
      expect(urls.some((url) => url.includes("incluir_inactivos"))).toBe(false);
      expect(
        urls.some((url) => url.includes("/api/profesionales?")),
      ).toBe(false);
    },
  );

  it.each([
    "/staff/admin/profesionales",
    "/staff/admin/usuarios",
    "/staff/admin/reportes",
  ])(
    "test_ruta_admin_sin_sesion_redirige_a_login",
    async (ruta) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      fetchMock.mockResolvedValueOnce(
        json({ detail: "No autenticado" }, 401),
      );

      renderApp(ruta);

      expect(
        await screen.findByRole("heading", { name: /iniciar sesión/i }),
      ).toBeDefined();
    },
  );

  it.each(["/", "/no-existe-xyz"])(
    "test_ruta_publica_%s_no_pide_sesion",
    (ruta) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      renderApp(ruta);

      expect(
        screen.queryByRole("heading", { name: /iniciar sesión/i }),
      ).toBeNull();
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );
});

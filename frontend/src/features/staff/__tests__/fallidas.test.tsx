/**
 * Panel de notificaciones fallidas §9: primera página con `limit=20`, cursor
 * opaco con deduplicación, estado vacío y errores 400/401/403/429; solo
 * recepción/admin. Capa: integración (router en memoria, fetch en el borde).
 * # AC frontend-agenda-staff/Panel de notificaciones fallidas
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const HOY = "2026-11-14";

type Rol = "recepcion" | "odontologo";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const meOdontologo = {
  email: "odontologo@ficticio.test",
  rol: "odontologo",
  profesional_id: ID_A,
};

function mePorRol(rol: Rol): unknown {
  return rol === "odontologo" ? meOdontologo : meRecepcion;
}

function fallida(
  id: string,
  overrides: Record<string, unknown> = {},
): unknown {
  return {
    id,
    turno_id: `turno-${id}`,
    tipo: "recordatorio",
    intentos: 3,
    error: "SMTP timeout",
    enviar_en: "2026-11-13T11:00:00Z",
    paciente_nombre: "Paciente Ficticio",
    paciente_email: "paciente@ficticio.test",
    inicio: `${HOY}T14:00:00-03:00`,
    fin: `${HOY}T14:30:00-03:00`,
    ...overrides,
  };
}

function pagina(items: unknown[], nextCursor: string | null): unknown {
  return { items, next_cursor: nextCursor };
}

function json(
  payload: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderNotificaciones(
  initialEntries: string[] = ["/staff/notificaciones"],
): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, { initialEntries });
  render(<RouterProvider router={router} />);
  return router;
}

function urlsDe(mock: ReturnType<typeof vi.fn>, sufijo: string): string[] {
  return mock.mock.calls
    .map((call) => call[0])
    .filter(
      (url): url is string => typeof url === "string" && url.includes(sufijo),
    );
}

function abrirCon(
  fetchMock: ReturnType<typeof vi.fn>,
  rol: Rol,
  respuesta: Response,
): void {
  fetchMock
    .mockResolvedValueOnce(json(mePorRol(rol)))
    .mockResolvedValueOnce(respuesta);
  renderNotificaciones();
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("notificaciones fallidas §9", () => {
  it("test_primera_pagina_muestra_campos_y_pide_limit_20", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json(pagina([fallida("notif-1")], null)),
    );

    const lista = await screen.findByRole("list", {
      name: /notificaciones fallidas/i,
    });
    const item = within(lista).getByRole("listitem");

    expect(within(item).getByText(/recordatorio/i)).toBeDefined();
    expect(within(item).getByText(/3 intentos/i)).toBeDefined();
    expect(within(item).getByText(/SMTP timeout/)).toBeDefined();
    expect(within(item).getByText(/Paciente Ficticio/)).toBeDefined();
    expect(within(item).getByText(/paciente@ficticio\.test/)).toBeDefined();
    expect(within(item).getByText(/14\/11\/2026 14:00–14:30/)).toBeDefined();
    expect(within(item).getByText(/13\/11\/2026 08:00/)).toBeDefined();

    const urls = urlsDe(fetchMock, "/api/notificaciones/fallidas");
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("limit=20");
    expect(urls[0]).not.toContain("cursor=");
  });

  it("test_cargar_mas_deduplica_por_id_y_agota_el_cursor", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json(
        pagina([fallida("notif-1"), fallida("notif-2")], "cursor-1"),
      ),
    );

    const lista = await screen.findByRole("list", {
      name: /notificaciones fallidas/i,
    });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(2);

    fetchMock.mockResolvedValueOnce(
      json(
        pagina(
          [fallida("notif-2"), fallida("notif-3")],
          null,
        ),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /cargar más/i }));

    await waitFor(() => {
      expect(within(lista).getAllByRole("listitem")).toHaveLength(3);
    });
    expect(
      urlsDe(fetchMock, "cursor=cursor-1"),
    ).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /cargar más/i }),
    ).toBeNull();
  });

  it("test_sin_fallidas_muestra_estado_vacio", async () => {
    const fetchMock = stubFetch();
    abrirCon(fetchMock, "recepcion", json(pagina([], null)));

    expect(
      await screen.findByText(/no hay notificaciones fallidas/i),
    ).toBeDefined();
    expect(
      screen.queryByRole("list", { name: /notificaciones fallidas/i }),
    ).toBeNull();
  });

  it("test_cursor_invalido_reinicia_el_listado_y_avisa", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json(pagina([fallida("notif-1")], "cursor-1")),
    );

    const lista = await screen.findByRole("list", {
      name: /notificaciones fallidas/i,
    });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(1);

    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "cursor",
              error: "cursor inválido",
              tipo: "cursor_invalido",
            },
          ],
        },
        400,
      ),
    );
    fetchMock.mockResolvedValueOnce(
      json(pagina([fallida("notif-1")], null)),
    );

    fireEvent.click(screen.getByRole("button", { name: /cargar más/i }));

    expect(
      await screen.findByText(/cursor dejó de ser válido/i),
    ).toBeDefined();
    expect(within(lista).getAllByRole("listitem")).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /cargar más/i }),
    ).toBeNull();
    expect(
      urlsDe(fetchMock, "/api/notificaciones/fallidas"),
    ).toHaveLength(3);
  });

  it("test_sesion_expirada_redirige_al_login", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json({ detail: "sesión expirada" }, 401),
    );

    expect(
      await screen.findByRole("heading", { name: /iniciar sesión/i }),
    ).toBeDefined();
    expect(screen.getByText(/tu sesión expiró/i)).toBeDefined();
  });

  it("test_403_muestra_mensaje_generico_sin_reintentar", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json({ detail: "sin permiso" }, 403),
    );

    expect(
      await screen.findByText(/no tenés permiso para esta acción/i),
    ).toBeDefined();
    expect(
      screen.queryByRole("button", { name: /reintentar/i }),
    ).toBeNull();
  });

  it("test_429_muestra_la_espera_de_retry_after", async () => {
    const fetchMock = stubFetch();
    abrirCon(
      fetchMock,
      "recepcion",
      json({ detail: "rate limit" }, 429, { "Retry-After": "7" }),
    );

    expect(
      await screen.findByText(/esperá 7 segundos/i),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: /reintentar/i }),
    ).toBeDefined();
  });

  it("test_odontologo_no_ve_el_enlace_ni_puede_acceder_al_panel", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meOdontologo));
    renderNotificaciones(["/staff/notificaciones"]);

    expect(
      await screen.findByText(/no tenés permiso para esta acción/i),
    ).toBeDefined();
    expect(
      screen.queryByRole("link", { name: /notificaciones fallidas/i }),
    ).toBeNull();
    expect(
      urlsDe(fetchMock, "/api/notificaciones/fallidas"),
    ).toHaveLength(0);
  });
});

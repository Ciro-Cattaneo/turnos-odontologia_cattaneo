/** Cancelación por token (capa: integración, fetch mockeado en el borde). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Cancelar } from "../Cancelar";

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const fetchMock = vi.fn<FetchLike>();

const TURNO_ID = "22222222-2222-4222-8222-222222222222";
const OTRO_ID = "44444444-4444-4444-8444-444444444444";
const TOKEN = "33333333-3333-4333-8333-333333333333";
const CONTACTO = "consultorio@ejemplo.test";

const confirmacion = {
  id: TURNO_ID,
  estado: "cancelado",
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
  notificaciones_encoladas: true,
  mensaje: "El turno fue cancelado correctamente.",
};

const generico = /link no es válido/i;

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function urlCancelar(params: Record<string, string>): string {
  const search = new URLSearchParams(params).toString();
  return `/cancelar?${search}`;
}

type MemoryRouterInstance = ReturnType<typeof createMemoryRouter>;

function renderCancel(params: Record<string, string>): MemoryRouterInstance {
  const router = createMemoryRouter(
    [{ path: "/cancelar", element: <Cancelar /> }],
    { initialEntries: [urlCancelar(params)] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

function valoresValidos(): Record<string, string> {
  return { token: TOKEN, id: TURNO_ID };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("página /cancelar", () => {
  it("test_cancelar_token_valido_muestra_confirmacion_generica_sin_datos", () => {
    renderCancel(valoresValidos());

    expect(screen.getByText(/querés cancelar este turno/i)).toBeDefined();
    expect(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    ).toBeDefined();
    expect(screen.queryByText(/Dra\./)).toBeNull();
    expect(screen.queryByText(/Paciente Ficticio/i)).toBeNull();
    expect(screen.queryByText(/10\/11\/2026/)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("test_cancelar_confirmacion_200_muestra_exito", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(confirmacion));

    renderCancel(valoresValidos());
    fireEvent.click(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(
      await screen.findByText(/cancelación confirmada/i),
    ).toBeDefined();
    expect(
      screen.getByText("El turno fue cancelado correctamente."),
    ).toBeDefined();
    expect(screen.getByText(/Estado del turno:\s*cancelado/)).toBeDefined();
    expect(screen.queryByText(/Dra\./)).toBeNull();
    expect(screen.queryByText(/Paciente Ficticio/i)).toBeNull();
    expect(screen.queryByText(/10\/11\/2026/)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain(`/api/turnos/${TURNO_ID}`);
    expect(String(url)).toContain(`token=${TOKEN}`);
    expect(init?.method).toBe("DELETE");
  });

  it("test_cancelar_sin_token_muestra_generico_sin_formulario_dni", () => {
    renderCancel({ id: TURNO_ID });

    expect(screen.getByRole("alert").textContent).toMatch(generico);
    expect(screen.queryByLabelText(/dni/i)).toBeNull();
    expect(screen.queryByLabelText(/teléfono/i)).toBeNull();
    expect(screen.queryByText(/mis turnos/i)).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("test_cancelar_url_solo_token_e_id_sin_datos_paciente", () => {
    const router = renderCancel(valoresValidos());

    const searchParams = new URLSearchParams(router.state.location.search);
    const claves = [...searchParams.keys()].sort();
    expect(claves).toEqual(["id", "token"]);
    const url = `${router.state.location.pathname}${router.state.location.search}`;
    for (const dato of [
      "Paciente Ficticio Test",
      "30000001",
      "1100000001",
      "Obra Social Test",
      "paciente@ejemplo.test",
    ]) {
      expect(url).not.toContain(dato);
    }
  });

  it("test_cancelar_422_fuera_de_plazo_muestra_contacto", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: {
            codigo: "cancelacion_fuera_de_plazo",
            mensaje: "La cancelación fuera de plazo no está permitida.",
            contacto: CONTACTO,
          },
        },
        422,
      ),
    );

    renderCancel(valoresValidos());
    fireEvent.click(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(
      await screen.findByText(/la cancelación fuera de plazo no está permitida/i),
    ).toBeDefined();
    expect(screen.getByText(CONTACTO)).toBeDefined();
    expect(
      screen.queryByRole("button", { name: /confirmar cancelación/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /reintentar/i })).toBeNull();
  });

  it("test_cancelar_422_turno_ya_cancelado_sin_contacto_ni_reintento", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: {
            codigo: "turno_ya_cancelado",
            mensaje: "El turno ya estaba cancelado.",
          },
        },
        422,
      ),
    );

    renderCancel(valoresValidos());
    fireEvent.click(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(await screen.findByText(/el turno ya estaba cancelado/i)).toBeDefined();
    expect(screen.queryByText(CONTACTO)).toBeNull();
    expect(screen.queryByRole("button", { name: /reintentar/i })).toBeNull();
  });

  it.each([403, 404])(
    "test_cancelar_403_y_404_muestran_mismo_generico (%i)",
    async (status) => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ detail: "No autorizado" }, status),
      );

      renderCancel(valoresValidos());
      fireEvent.click(
        screen.getByRole("button", { name: /confirmar cancelación/i }),
      );

      const alerta = await screen.findByRole("alert");
      expect(alerta.textContent).toMatch(generico);
      expect(screen.queryByText(/Dra\./)).toBeNull();
      expect(screen.queryByText(/Paciente Ficticio/i)).toBeNull();
      expect(screen.queryByText(/10\/11\/2026/)).toBeNull();
    },
  );

  it.each([
    ["sin id", { token: TOKEN }],
    ["id malformado", { token: TOKEN, id: "no-es-uuid" }],
  ])(
    "test_cancelar_id_ausente_o_malformado_muestra_generico (%s)",
    (_caso, params) => {
      renderCancel(params);

      expect(screen.getByRole("alert").textContent).toMatch(generico);
      expect(screen.queryByRole("button")).toBeNull();
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("test_cancelar_token_no_corresponde_al_id_403_generico", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "No autorizado" }, 403),
    );

    renderCancel({ token: TOKEN, id: OTRO_ID });
    fireEvent.click(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    );

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(generico);
    expect(screen.queryByText(/Dra\./)).toBeNull();
    expect(screen.queryByText(/Paciente Ficticio/i)).toBeNull();
    expect(screen.queryByText(/10\/11\/2026/)).toBeNull();
  });

  it("test_cancelar_429_muestra_espera_retry_after", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Demasiados intentos" }, 429, {
        "Retry-After": "7",
      }),
    );

    renderCancel(valoresValidos());
    fireEvent.click(
      screen.getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(await screen.findByText(/demasiados intentos/i)).toBeDefined();
    expect(screen.getByText(/7 segundos/i)).toBeDefined();
  });
});

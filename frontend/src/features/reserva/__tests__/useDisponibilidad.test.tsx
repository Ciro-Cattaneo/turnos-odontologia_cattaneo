/** Estado de búsqueda de disponibilidad (capa: unit/componente, R2/R11/R14). */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDisponibilidad } from "../hooks/useDisponibilidad";

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const fetchMock = vi.fn<FetchLike>();
const PROF_ID = "11111111-1111-4111-8111-111111111111";
const FECHA = "2026-11-10";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const disponible = {
  profesional_id: PROF_ID,
  slots: [
    {
      inicio: "2026-11-10T09:00:00-03:00",
      fin: "2026-11-10T09:30:00-03:00",
      duracion_min: 30,
    },
  ],
  ultima_actualizacion: null,
};

function Harness(): JSX.Element {
  const { state, buscar, reintentar } = useDisponibilidad();
  return (
    <div>
      <button
        type="button"
        disabled={state.status === "loading"}
        onClick={() => {
          void buscar(PROF_ID, FECHA);
        }}
      >
        Buscar horarios
      </button>
      {state.status === "loading" && <p role="status">Cargando horarios…</p>}
      {state.status === "empty" && <p>Sin horarios disponibles para esa fecha.</p>}
      {state.status === "error" && state.error !== null && (
        <div role="alert">
          <p>{state.error.message}</p>
          {(state.error.kind === "network" || state.error.kind === "unexpected") && (
            <button type="button" onClick={reintentar}>
              Reintentar
            </button>
          )}
        </div>
      )}
      {state.status === "success" && (
        <ul>
          {state.slots.map((slot) => (
            <li key={slot.inicio}>{slot.inicio}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useDisponibilidad", () => {
  it("test_disponibilidad_muestra_carga_y_deshabilita_acciones", async () => {
    let resolver: (response: Response) => void = () => undefined;
    fetchMock.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolver = resolve;
      }),
    );

    render(<Harness />);
    const boton = screen.getByRole("button", { name: "Buscar horarios" });
    fireEvent.click(boton);

    expect(await screen.findByText(/cargando horarios/i)).toBeDefined();
    expect((boton as HTMLButtonElement).disabled).toBe(true);

    resolver(jsonResponse(disponible));
    await waitFor(() => {
      expect(screen.queryByText(/cargando horarios/i)).toBeNull();
    });
  });

  it("test_disponibilidad_error_de_red_muestra_reintento", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(disponible));

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Buscar horarios" }));

    expect(await screen.findByText(/no pudimos conectarnos/i)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(
      await screen.findByText("2026-11-10T09:00:00-03:00"),
    ).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("test_disponibilidad_404_profesional_invita_recargar", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "No encontrado" }, 404),
    );

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Buscar horarios" }));

    expect(
      await screen.findByText(/profesional no está disponible/i),
    ).toBeDefined();
    expect(screen.getByText(/recargá la lista/i)).toBeDefined();
  });

  it("test_disponibilidad_429_muestra_espera", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Demasiadas consultas" }, 429, {
        "Retry-After": "9",
      }),
    );

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Buscar horarios" }));

    expect(await screen.findByText(/demasiados intentos/i)).toBeDefined();
    expect(screen.getByText(/9 segundos/i)).toBeDefined();
    expect(screen.queryByRole("button", { name: /reintentar/i })).toBeNull();
  });

  it("test_disponibilidad_sin_slots_muestra_estado_vacio", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...disponible, slots: [] }),
    );

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Buscar horarios" }));

    expect(
      await screen.findByText(/sin horarios disponibles/i),
    ).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

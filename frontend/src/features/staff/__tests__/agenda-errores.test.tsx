/**
 * Errores de agenda staff: 404 con recarga de profesionales, 403 genérico,
 * 429 con espera y red conservando la selección (capa: integración, fetch de
 * borde). # AC frontend-agenda-staff/Agenda día/semana — §5.4.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";
import { addDias, hoyEnConsultorio } from "../../../shared/format";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const HOY = hoyEnConsultorio();

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const profesionalA = {
  id: ID_A,
  nombre: "Dra. Alpha Ficticia",
  especialidad: "Clínica",
  matricula: null,
  duracion_default_min: 30,
  ultima_actualizacion: null,
};

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

function renderAgenda(): void {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/agenda"],
  });
  render(<RouterProvider router={router} />);
}

function rutaDe(url: string): string {
  const parsed = new URL(url, "http://test.local");
  return `${parsed.pathname}${parsed.search}`;
}

function urlsDe(mock: ReturnType<typeof vi.fn>, sufijo: string): string[] {
  return mock.mock.calls
    .map((call) => call[0])
    .filter((url): url is string => typeof url === "string")
    .map((url) => rutaDe(url))
    .filter((url) => url.includes(sufijo));
}

function urlAgenda(id: string, fecha: string): string {
  return `/api/profesionales/${id}/agenda?vista=dia&fecha=${fecha}`;
}

function agendaConLibre(fecha: string = HOY): unknown {
  return {
    profesional_id: ID_A,
    vista: "dia",
    dias: [
      {
        fecha,
        franjas: [
          {
            tipo: "libre",
            inicio: `${fecha}T09:00:00-03:00`,
            fin: `${fecha}T09:30:00-03:00`,
            duracion_min: 30,
          },
        ],
      },
    ],
    next_cursor: addDias(fecha, 1),
    ultima_actualizacion: null,
  };
}

const profesionalesPage = { items: [profesionalA], next_cursor: null };

interface CasoError {
  nombre: string;
  preparar: (fetchMock: ReturnType<typeof vi.fn>) => void;
  mensaje: RegExp;
  accion: RegExp | null;
}

const casos: CasoError[] = [
  {
    nombre: "404",
    preparar: (fetchMock) => {
      fetchMock.mockResolvedValueOnce(json({ detail: "No encontrado" }, 404));
    },
    mensaje: /no está disponible/i,
    accion: /recargar profesionales/i,
  },
  {
    nombre: "403",
    preparar: (fetchMock) => {
      fetchMock.mockResolvedValueOnce(json({ detail: "Sin permiso" }, 403));
    },
    mensaje: /no tenés permiso para esta acción/i,
    accion: null,
  },
  {
    nombre: "429",
    preparar: (fetchMock) => {
      fetchMock.mockResolvedValueOnce(
        json({ detail: "Demasiados intentos" }, 429, {
          "Retry-After": "45",
        }),
      );
    },
    mensaje: /45 segundos/i,
    accion: /reintentar/i,
  },
  {
    nombre: "red",
    preparar: (fetchMock) => {
      fetchMock.mockRejectedValueOnce(new TypeError("sin red"));
    },
    mensaje: /no pudimos conectarnos/i,
    accion: /reintentar/i,
  },
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("errores de agenda", () => {
  it.each(casos.map((caso) => [caso.nombre, caso] as const))(
    "test_agenda_%s_muestra_error_accionable_sin_datos_de_paciente",
    async (_nombre, caso) => {
      const { preparar, mensaje, accion } = caso;
      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(json(profesionalesPage));
      preparar(fetchMock);

      renderAgenda();

      expect(await screen.findByText(mensaje)).toBeDefined();
      expect(screen.queryByText("Paciente Ficticio")).toBeNull();
      expect(fetchMock).toHaveBeenCalledTimes(3);
      if (accion !== null) {
        expect(screen.getByRole("button", { name: accion })).toBeDefined();
      }
    },
  );

  it("test_404_recargar_profesionales_vuelve_a_consultar_la_lista", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(profesionalesPage))
      .mockResolvedValueOnce(json({ detail: "No encontrado" }, 404))
      .mockResolvedValueOnce(json(profesionalesPage))
      .mockResolvedValueOnce(json(agendaConLibre()));

    renderAgenda();
    await screen.findByText(/no está disponible/i);

    fireEvent.click(
      screen.getByRole("button", { name: /recargar profesionales/i }),
    );

    await waitFor(() =>
      expect(
        urlsDe(fetchMock, "").filter((url) => url === "/api/profesionales"),
      ).toHaveLength(2),
    );
    expect(await screen.findByText("Libre")).toBeDefined();
  });

  it("test_error_de_red_conserva_la_seleccion_y_reintenta_la_misma_clave", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(profesionalesPage))
      .mockRejectedValueOnce(new TypeError("sin red"))
      .mockResolvedValueOnce(json(agendaConLibre()));

    renderAgenda();
    await screen.findByText(/no pudimos conectarnos/i);

    const selector = screen.getByLabelText("Profesional") as HTMLSelectElement;
    expect(selector.value).toBe(ID_A);
    expect(selector.disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(await screen.findByText("Libre")).toBeDefined();
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, HOY),
      urlAgenda(ID_A, HOY),
    ]);
  });
});

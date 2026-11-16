/**
 * §6.5 — privacidad de las pantallas admin: ni lo tipeado en los formularios ni
 * el profesional elegido viajan por `location.pathname`/`search` (Ley 25.326).
 * Solo el filtro explícito del reporte va en la query del `fetch`.
 * Capa: integración con router en memoria.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../../App";

const meAdmin = {
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
};

const PROF_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const profesionalA = {
  id: PROF_A,
  nombre: "Dra. Ficticia Uno",
  matricula: "MP-0001",
  especialidad: "Ortodoncia",
  duracion_default_min: 45,
  activo: true,
  ultima_actualizacion: null,
};
const profesionalesPage = { items: [profesionalA], next_cursor: null };
const usuariosPage = {
  items: [
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      email: "recepcion@cattaneo.test",
      rol: "recepcion",
      profesional_id: null,
      activo: true,
    },
  ],
  next_cursor: null,
};
const reporteVacio = {
  desde: "2026-10-18",
  hasta: "2026-11-16",
  zona: "America/Argentina/Buenos_Aires",
  items: [],
  totales: {
    turnos: 0,
    atendidos: 0,
    ausentes: 0,
    cancelados: 0,
    pendientes: 0,
    minutos_ocupados: 0,
    minutos_disponibles: 0,
    porcentaje_ocupacion: null,
  },
};

const NOMBRE = "Ficticia Reservada";
const MATRICULA = "MP-9001";
const ESPECIALIDAD = "Ortodoncia Reservada";
const EMAIL = "reservado@cattaneo.test";
const PASSWORD = "ficticia-segura-123";

const DATOS_INGRESADOS = [NOMBRE, MATRICULA, ESPECIALIDAD, EMAIL, PASSWORD];

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function pathDe(url: string): string {
  return new URL(url, "http://test.local").pathname;
}

type Handler = (path: string, method: string) => Response | undefined;

function stubApi(handler: Handler): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((entrada: unknown, init?: RequestInit) => {
    const respuesta = handler(pathDe(String(entrada)), init?.method ?? "GET");
    if (respuesta === undefined) {
      throw new Error(`fetch no esperado: ${init?.method ?? "GET"} ${entrada}`);
    }
    return Promise.resolve(respuesta);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubAdmin(): ReturnType<typeof vi.fn> {
  return stubApi((path) => {
    if (path === "/api/auth/me") {
      return json(meAdmin);
    }
    if (path === "/api/profesionales") {
      return json(profesionalesPage);
    }
    if (path === "/api/usuarios-staff") {
      return json(usuariosPage);
    }
    if (path === "/api/reportes/ocupacion") {
      return json(reporteVacio);
    }
    return undefined;
  });
}

function renderAdmin(
  ruta: string,
): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, { initialEntries: [ruta] });
  render(<RouterProvider router={router} />);
  return router;
}

function urlActual(router: ReturnType<typeof createMemoryRouter>): string {
  const { pathname, search, hash } = router.state.location;
  return `${pathname}${search}${hash}`;
}

function urlsLlamadas(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map((call) => String(call[0]));
}

function expectUrlLimpia(
  router: ReturnType<typeof createMemoryRouter>,
  esperada: string,
): void {
  expect(urlActual(router)).toBe(esperada);
  for (const dato of DATOS_INGRESADOS) {
    expect(urlActual(router)).not.toContain(dato);
    expect(urlActual(router)).not.toContain(encodeURIComponent(dato));
  }
}

function expectFetchSinDatos(fetchMock: ReturnType<typeof vi.fn>): void {
  const urls = urlsLlamadas(fetchMock);
  expect(urls.length).toBeGreaterThan(0);
  for (const url of urls) {
    for (const dato of DATOS_INGRESADOS) {
      expect(url).not.toContain(dato);
      expect(url).not.toContain(encodeURIComponent(dato));
    }
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("privacidad de las pantallas admin", () => {
  it("test_pantallas_admin_no_ponen_datos_en_la_url", async () => {
    const fetchProfesionales = stubAdmin();
    const routerProfesionales = renderAdmin("/staff/admin/profesionales");

    await screen.findByRole("heading", { level: 1, name: "Profesionales" });
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    const alta = await screen.findByRole("form", {
      name: /alta de profesional/i,
    });
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: NOMBRE },
    });
    fireEvent.change(screen.getByLabelText("Matrícula"), {
      target: { value: MATRICULA },
    });
    fireEvent.change(screen.getByLabelText("Especialidad"), {
      target: { value: ESPECIALIDAD },
    });
    fireEvent.click(within(alta).getByRole("button", { name: /cancelar/i }));
    fireEvent.click(screen.getByRole("button", { name: /^editar$/i }));
    await screen.findByRole("form", { name: /editar profesional/i });
    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));

    expectUrlLimpia(routerProfesionales, "/staff/admin/profesionales");
    expectFetchSinDatos(fetchProfesionales);

    cleanup();
    vi.unstubAllGlobals();

    const fetchUsuarios = stubAdmin();
    const routerUsuarios = renderAdmin("/staff/admin/usuarios");
    await screen.findByRole("heading", { level: 1, name: "Usuarios staff" });
    fireEvent.click(screen.getByRole("button", { name: /agregar usuario/i }));
    const altaUsuario = await screen.findByRole("form", {
      name: /alta de usuario staff/i,
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: EMAIL },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: PASSWORD },
    });
    fireEvent.click(
      within(altaUsuario).getByRole("button", { name: /cancelar/i }),
    );

    expectUrlLimpia(routerUsuarios, "/staff/admin/usuarios");
    expectFetchSinDatos(fetchUsuarios);

    cleanup();
    vi.unstubAllGlobals();

    const fetchReporte = stubAdmin();
    const routerReporte = renderAdmin("/staff/admin/reportes");
    await screen.findByRole("heading", { level: 1, name: "Reportes" });
    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_A },
    });
    fireEvent.click(screen.getByRole("button", { name: /^consultar$/i }));
    await waitFor(() =>
      expect(
        urlsLlamadas(fetchReporte).filter(
          (url) => pathDe(url) === "/api/reportes/ocupacion",
        ),
      ).toHaveLength(2),
    );

    expect(urlActual(routerReporte)).toBe("/staff/admin/reportes");
    expect(urlActual(routerReporte)).not.toContain(profesionalA.nombre);
    const urlsReporte = urlsLlamadas(fetchReporte).filter(
      (url) => pathDe(url) === "/api/reportes/ocupacion",
    );
    const urlReporte = urlsReporte[urlsReporte.length - 1] ?? "";
    expect(
      new URL(urlReporte, "http://test.local").searchParams.get(
        "profesional_id",
      ),
    ).toBe(PROF_A);
    expectFetchSinDatos(fetchReporte);
  });
});

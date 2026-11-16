/**
 * §6.6 — estados comunes de las pantallas admin ante `401` y `429`: el `401`
 * descarta el estado y redirige a login sin datos, y el `429` muestra la espera
 * indicada por `Retry-After` sin reintento automático (solo manual).
 * Capa: integración parametrizada por las tres pantallas.
 */

import { render, screen } from "@testing-library/react";
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

interface Pantalla {
  ruta: string;
  endpoint: string;
  titulo: string;
  dato: string;
  respuesta: unknown;
}

const PANTALLAS: Pantalla[] = [
  {
    ruta: "/staff/admin/profesionales",
    endpoint: "/api/profesionales",
    titulo: "Profesionales",
    dato: profesionalA.nombre,
    respuesta: profesionalesPage,
  },
  {
    ruta: "/staff/admin/usuarios",
    endpoint: "/api/usuarios-staff",
    titulo: "Usuarios staff",
    dato: "recepcion@cattaneo.test",
    respuesta: usuariosPage,
  },
  {
    ruta: "/staff/admin/reportes",
    endpoint: "/api/reportes/ocupacion",
    titulo: "Reportes",
    dato: "Zona: America/Argentina/Buenos_Aires",
    respuesta: reporteVacio,
  },
];

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function conEspera(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 429,
    headers: { "Content-Type": "application/json", "Retry-After": "30" },
  });
}

function pathDe(url: string): string {
  return new URL(url, "http://test.local").pathname;
}

function stubPantalla(
  pantalla: Pantalla,
  respuestaFallo: Response,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((entrada: unknown, init?: RequestInit) => {
    const path = pathDe(String(entrada));
    const method = init?.method ?? "GET";
    if (path === "/api/auth/me") {
      return Promise.resolve(json(meAdmin));
    }
    if (path === pantalla.endpoint && method === "GET") {
      return Promise.resolve(respuestaFallo);
    }
    if (path === "/api/profesionales" && method === "GET") {
      return Promise.resolve(json(profesionalesPage));
    }
    if (path === "/api/usuarios-staff" && method === "GET") {
      return Promise.resolve(json(usuariosPage));
    }
    if (path === "/api/reportes/ocupacion" && method === "GET") {
      return Promise.resolve(json(reporteVacio));
    }
    throw new Error(`fetch no esperado: ${method} ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAdmin(pantalla: Pantalla): void {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [pantalla.ruta],
  });
  render(<RouterProvider router={router} />);
}

function llamadasA(
  fetchMock: ReturnType<typeof vi.fn>,
  endpoint: string,
): number {
  return fetchMock.mock.calls.filter(
    (call) => pathDe(String(call[0])) === endpoint,
  ).length;
}

function esperar(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("estados 401 y 429 de las pantallas admin", () => {
  it.each(PANTALLAS)(
    "test_pantallas_admin_401_redirigen_a_login_sin_datos_en_$endpoint",
    async (pantalla) => {
      stubPantalla(pantalla, json({ detail: "sesión expirada" }, 401));

      renderAdmin(pantalla);

      expect(
        await screen.findByRole("heading", { name: /iniciar sesión/i }),
      ).toBeDefined();
      expect(
        screen.queryByRole("heading", { level: 1, name: pantalla.titulo }),
      ).toBeNull();
      expect(screen.queryByText(pantalla.dato)).toBeNull();
    },
  );

  it.each(PANTALLAS)(
    "test_pantallas_admin_429_muestran_espera_sin_reintento_automatico_en_$endpoint",
    async (pantalla) => {
      const fetchMock = stubPantalla(
        pantalla,
        conEspera({ detail: "demasiados intentos" }),
      );

      renderAdmin(pantalla);

      const mensaje = await screen.findByText(/demasiados intentos/i);
      expect(mensaje.textContent).toContain("30");
      expect(
        screen.getByRole("button", { name: /reintentar/i }),
      ).toBeDefined();
      expect(llamadasA(fetchMock, pantalla.endpoint)).toBe(1);

      await esperar(60);
      expect(llamadasA(fetchMock, pantalla.endpoint)).toBe(1);
    },
  );
});

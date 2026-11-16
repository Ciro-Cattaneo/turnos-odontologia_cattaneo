/**
 * §6.3 — a11y de los formularios y filtros admin: cada campo tiene etiqueta
 * asociada, el error expone `aria-invalid` + `aria-describedby`, se anuncia por
 * `role="alert"` y el foco va al primer campo inválido; el éxito se anuncia en
 * la región `aria-live` de la pantalla. Capa: integración con fetch de borde.
 */

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../../App";
import { addDias, hoyEnConsultorio } from "../../../../shared/format";

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

function renderAdmin(ruta: string): void {
  const router = createMemoryRouter(appRoutes, { initialEntries: [ruta] });
  render(<RouterProvider router={router} />);
}

function stubAdminBase(
  extra: (path: string, method: string) => Response | undefined,
): ReturnType<typeof vi.fn> {
  return stubApi((path, method) => {
    if (path === "/api/auth/me") {
      return json(meAdmin);
    }
    if (path === "/api/profesionales") {
      return json(profesionalesPage);
    }
    return extra(path, method);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("a11y de formularios admin", () => {
  it("test_formularios_admin_asocian_labels_y_anuncian_errores", async () => {
    stubAdminBase(() => undefined);
    renderAdmin("/staff/admin/profesionales");

    await screen.findByRole("heading", { level: 1, name: "Profesionales" });
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    const form = await screen.findByRole("form", {
      name: /alta de profesional/i,
    });
    for (const etiqueta of [
      "Nombre",
      "Matrícula",
      "Especialidad",
      "Duración",
    ]) {
      expect(within(form).getByLabelText(etiqueta)).toBeDefined();
    }

    fireEvent.click(
      within(form).getByRole("button", { name: /crear profesional/i }),
    );

    const nombre = within(form).getByLabelText("Nombre");
    await waitFor(() =>
      expect(nombre.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(nombre.getAttribute("aria-describedby")).toBe(
      "prof-alta-nombre-error",
    );
    const mensaje = document.getElementById("prof-alta-nombre-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(mensaje?.textContent).toContain("obligatorio");
    await waitFor(() => expect(document.activeElement).toBe(nombre));
  });

  it("test_formularios_admin_de_usuarios_asocian_labels_y_anuncian_errores", async () => {
    stubAdminBase((path) =>
      path === "/api/usuarios-staff" ? json(usuariosPage) : undefined,
    );
    renderAdmin("/staff/admin/usuarios");

    await screen.findByRole("heading", { level: 1, name: "Usuarios staff" });
    fireEvent.click(screen.getByRole("button", { name: /agregar usuario/i }));
    const form = await screen.findByRole("form", {
      name: /alta de usuario staff/i,
    });
    for (const etiqueta of ["Email", "Contraseña", "Rol"]) {
      expect(within(form).getByLabelText(etiqueta)).toBeDefined();
    }

    fireEvent.click(
      within(form).getByRole("button", { name: /crear usuario/i }),
    );

    const email = within(form).getByLabelText("Email");
    await waitFor(() => expect(email.getAttribute("aria-invalid")).toBe("true"));
    expect(email.getAttribute("aria-describedby")).toBe("usr-alta-email-error");
    const mensaje = document.getElementById("usr-alta-email-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(mensaje?.textContent).toContain("obligatorio");
    await waitFor(() => expect(document.activeElement).toBe(email));
  });

  it("test_filtros_reporte_asocian_labels_y_anuncian_errores", async () => {
    stubAdminBase((path) =>
      path === "/api/reportes/ocupacion" ? json(reporteVacio) : undefined,
    );
    renderAdmin("/staff/admin/reportes");

    await screen.findByRole("heading", { level: 1, name: "Reportes" });
    for (const etiqueta of ["Desde", "Hasta", "Profesional"]) {
      expect(screen.getByLabelText(etiqueta)).toBeDefined();
    }

    const hoy = hoyEnConsultorio();
    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: addDias(hoy, -366) },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: hoy },
    });
    fireEvent.click(screen.getByRole("button", { name: /^consultar$/i }));

    const hasta = screen.getByLabelText("Hasta");
    await waitFor(() => expect(hasta.getAttribute("aria-invalid")).toBe("true"));
    expect(hasta.getAttribute("aria-describedby")).toBe("reporte-hasta-error");
    const mensaje = document.getElementById("reporte-hasta-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(mensaje?.textContent).toContain("366");
    await waitFor(() => expect(document.activeElement).toBe(hasta));
  });

  it("test_alta_profesional_anuncia_exito_en_region_aria_live", async () => {
    let listados = 0;
    const creado = {
      ...profesionalA,
      id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      nombre: "Dra. Nueva Ficticia",
    };
    stubApi((path, method) => {
      if (path === "/api/auth/me") {
        return json(meAdmin);
      }
      if (path !== "/api/profesionales") {
        return undefined;
      }
      if (method === "POST") {
        return json(creado, 201);
      }
      listados += 1;
      return json(
        listados === 1
          ? profesionalesPage
          : { items: [creado], next_cursor: null },
      );
    });
    renderAdmin("/staff/admin/profesionales");

    await screen.findByRole("heading", { level: 1, name: "Profesionales" });
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    const form = await screen.findByRole("form", {
      name: /alta de profesional/i,
    });
    fireEvent.change(within(form).getByLabelText("Nombre"), {
      target: { value: "Dra. Nueva Ficticia" },
    });
    fireEvent.change(within(form).getByLabelText("Matrícula"), {
      target: { value: "MP-0009" },
    });
    fireEvent.click(
      within(form).getByRole("button", { name: /crear profesional/i }),
    );

    const aviso = await screen.findByText("Profesional creado.");
    expect(aviso.getAttribute("role")).toBe("status");
    expect(aviso.getAttribute("aria-live")).toBe("polite");
    await screen.findByText("Dra. Nueva Ficticia");
    expect(listados).toBe(2);
  });
});

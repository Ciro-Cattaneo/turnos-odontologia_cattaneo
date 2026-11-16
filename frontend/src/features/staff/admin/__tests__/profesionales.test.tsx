/**
 * Administración de profesionales (capa: integración, router en memoria).
 * Cubre FA listado/alta/edición/baja/reactivación y sus errores accionables.
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

const meAdmin = {
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
};

const PROF_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const PROF_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const PROF_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

const profesionalA = {
  id: PROF_A,
  nombre: "Dra. Ficticia Uno",
  matricula: "MP-0001",
  especialidad: "Ortodoncia",
  duracion_default_min: 45,
  activo: true,
  ultima_actualizacion: null,
};
const profesionalB = {
  id: PROF_B,
  nombre: "Dr. Ficticio Dos",
  matricula: null,
  especialidad: "Clínica",
  duracion_default_min: 30,
  activo: true,
  ultima_actualizacion: null,
};
const profesionalInactivo = {
  id: PROF_C,
  nombre: "Dra. Inactiva Ficticia",
  matricula: "MP-0003",
  especialidad: null,
  duracion_default_min: 30,
  activo: false,
  ultima_actualizacion: null,
};

const pageTodos = {
  items: [profesionalA, profesionalB, profesionalInactivo],
  next_cursor: null,
};
const pageActivos = { items: [profesionalA, profesionalB], next_cursor: null };

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

function sesionYListado(
  fetchMock: ReturnType<typeof vi.fn>,
  page: unknown,
): void {
  fetchMock
    .mockResolvedValueOnce(json(meAdmin))
    .mockResolvedValueOnce(json(page));
}

function renderAdmin(): void {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/admin/profesionales"],
  });
  render(<RouterProvider router={router} />);
}

interface Llamada {
  url: string;
  method: string;
  body: unknown;
}

function llamadas(
  fetchMock: ReturnType<typeof vi.fn>,
  method: string,
): Llamada[] {
  const resultado: Llamada[] = [];
  for (const llamada of fetchMock.mock.calls) {
    const url = String(llamada[0]);
    const init = (llamada[1] ?? {}) as RequestInit;
    if (init.method === method) {
      resultado.push({
        url,
        method,
        body:
          typeof init.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      });
    }
  }
  return resultado;
}

function ultimaUrl(fetchMock: ReturnType<typeof vi.fn>): string {
  const llamadasHechas = fetchMock.mock.calls;
  return String(llamadasHechas[llamadasHechas.length - 1]?.[0] ?? "");
}

function cantGetProfesionales(fetchMock: ReturnType<typeof vi.fn>): number {
  return fetchMock.mock.calls.filter((llamada) => {
    const url = String(llamada[0]);
    const init = (llamada[1] ?? {}) as RequestInit;
    return (
      init.method === undefined && url.includes("/api/profesionales")
    );
  }).length;
}

function filaDe(nombre: string): HTMLElement {
  const texto = screen.getByText(nombre);
  const fila = texto.closest("li");
  if (fila === null) {
    throw new Error(`No se encontró la fila de ${nombre}`);
  }
  return fila;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("profesionales admin", () => {
  it("test_profesionales_listado_muestra_activos_e_inactivos", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();

    expect(await screen.findByText("Dra. Ficticia Uno")).toBeDefined();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("Inactivo")).toBeDefined();
    expect(screen.getAllByText("Activo")).toHaveLength(2);
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "incluir_inactivos=true",
    );
  });

  it("test_toggle_incluir_inactivos_cambia_la_consulta", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    const toggle = screen.getByRole("checkbox", {
      name: /incluir inactivos/i,
    });
    expect((toggle as HTMLInputElement).checked).toBe(true);

    fetchMock.mockResolvedValueOnce(json(pageActivos));
    fireEvent.click(toggle);

    await waitFor(() => {
      const ultima = ultimaUrl(fetchMock);
      expect(ultima).toContain("/api/profesionales");
      expect(ultima).not.toContain("incluir_inactivos");
    });

    fetchMock.mockResolvedValueOnce(json(pageTodos));
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(ultimaUrl(fetchMock)).toContain("incluir_inactivos=true");
    });
  });

  it("test_profesionales_listado_vacio_informa_sin_error", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, { items: [], next_cursor: null });

    renderAdmin();

    expect(
      await screen.findByText(/no hay profesionales para el filtro/i),
    ).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("test_profesionales_error_de_red_conserva_filtro_y_permite_reintentar", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meAdmin))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    renderAdmin();

    expect(await screen.findByText(/no pudimos conectarnos/i)).toBeDefined();
    const toggle = screen.getByRole("checkbox", {
      name: /incluir inactivos/i,
    });
    expect((toggle as HTMLInputElement).checked).toBe(true);

    fetchMock.mockResolvedValueOnce(json(pageTodos));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(await screen.findByText("Dra. Ficticia Uno")).toBeDefined();
    expect(ultimaUrl(fetchMock)).toContain("incluir_inactivos=true");
  });

  it("test_alta_profesional_valida_emite_post_y_refresca_listado", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );

    const creado = {
      id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      nombre: "Dra. Ficticia Nueva",
      matricula: "MP-0009",
      especialidad: "Ortodoncia",
      duracion_default_min: 45,
      activo: true,
      ultima_actualizacion: null,
    };
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Dra. Ficticia Nueva" },
    });
    fireEvent.change(screen.getByLabelText("Matrícula"), {
      target: { value: "MP-0009" },
    });
    fireEvent.change(screen.getByLabelText("Especialidad"), {
      target: { value: "Ortodoncia" },
    });
    fireEvent.change(screen.getByLabelText("Duración"), {
      target: { value: "45" },
    });

    fetchMock
      .mockResolvedValueOnce(json(creado, 201))
      .mockResolvedValueOnce(
        json({ items: [...pageTodos.items, creado], next_cursor: null }),
      );

    fireEvent.click(screen.getByRole("button", { name: /crear profesional/i }));

    expect(await screen.findByText("Profesional creado.")).toBeDefined();
    const [post] = llamadas(fetchMock, "POST");
    expect(post).toBeDefined();
    expect(post?.url).toContain("/api/profesionales");
    expect(post?.body).toEqual({
      nombre: "Dra. Ficticia Nueva",
      matricula: "MP-0009",
      especialidad: "Ortodoncia",
      duracion_default_min: 45,
    });
    expect(llamadas(fetchMock, "POST")).toHaveLength(1);
    expect(cantGetProfesionales(fetchMock)).toBe(2);
    expect(await screen.findByText("Dra. Ficticia Nueva")).toBeDefined();
  });

  it("test_alta_profesional_duracion_solo_ofrece_grilla_5_240", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );

    const select = screen.getByLabelText("Duración") as HTMLSelectElement;
    const opciones = within(select).getAllByRole("option");
    expect(opciones).toHaveLength(48);
    expect(opciones[0]?.getAttribute("value")).toBe("5");
    expect(opciones[opciones.length - 1]?.getAttribute("value")).toBe("240");
    expect(select.value).toBe("30");
    expect(screen.queryByRole("spinbutton")).toBeNull();
    expect(
      document.querySelector('input[name="duracion_default_min"]'),
    ).toBeNull();
  });

  it("test_alta_profesional_400_marca_solo_duracion_y_conserva_valores", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Dra. Ficticia Conservada" },
    });
    fireEvent.change(screen.getByLabelText("Matrícula"), {
      target: { value: "MP-0010" },
    });
    fireEvent.change(screen.getByLabelText("Duración"), {
      target: { value: "45" },
    });

    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "duracion_default_min",
              error: "La duración debe ser múltiplo de 5.",
              tipo: "value_error",
            },
          ],
        },
        400,
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /crear profesional/i }));

    const select = screen.getByLabelText("Duración");
    await waitFor(() =>
      expect(select.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(
      (screen.getByLabelText("Nombre") as HTMLInputElement).value,
    ).toBe("Dra. Ficticia Conservada");
    expect(
      screen.getByLabelText("Nombre").getAttribute("aria-invalid"),
    ).not.toBe("true");
    expect(screen.getByText(/múltiplo de 5/i)).toBeDefined();
    await waitFor(() => expect(document.activeElement).toBe(select));
    expect(screen.queryByText("Profesional creado.")).toBeNull();
    expect(cantGetProfesionales(fetchMock)).toBe(1);
  });

  it("test_alta_profesional_nombre_vacio_no_emite_post", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    fireEvent.change(screen.getByLabelText("Matrícula"), {
      target: { value: "MP-0011" },
    });

    fireEvent.click(screen.getByRole("button", { name: /crear profesional/i }));

    expect(llamadas(fetchMock, "POST")).toHaveLength(0);
    await waitFor(() =>
      expect(
        screen.getByLabelText("Nombre").getAttribute("aria-invalid"),
      ).toBe("true"),
    );
  });

  it("test_alta_profesional_403_muestra_falta_de_permiso_sin_refrescar", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      screen.getByRole("button", { name: /agregar profesional/i }),
    );
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Dra. Sin Permiso" },
    });

    fetchMock.mockResolvedValueOnce(json({ detail: "Sin permiso" }, 403));
    fireEvent.click(screen.getByRole("button", { name: /crear profesional/i }));

    expect(
      await screen.findByText("No tenés permiso para esta acción."),
    ).toBeDefined();
    expect(screen.queryByText("Profesional creado.")).toBeNull();
    expect(cantGetProfesionales(fetchMock)).toBe(1);
  });

  it("test_edicion_profesional_envia_put_con_campos_modificados", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      within(filaDe("Dra. Ficticia Uno")).getByRole("button", {
        name: "Editar",
      }),
    );

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Dra. Ficticia Editada" },
    });
    fireEvent.change(screen.getByLabelText("Duración"), {
      target: { value: "60" },
    });

    const actualizado = {
      ...profesionalA,
      nombre: "Dra. Ficticia Editada",
      duracion_default_min: 60,
    };
    fetchMock.mockResolvedValueOnce(json(actualizado));

    fireEvent.click(
      screen.getByRole("button", { name: /guardar cambios/i }),
    );

    expect(await screen.findByText("Dra. Ficticia Editada")).toBeDefined();
    const [put] = llamadas(fetchMock, "PUT");
    expect(put).toBeDefined();
    expect(put?.url).toContain(`/api/profesionales/${PROF_A}`);
    expect(put?.body).toEqual({
      nombre: "Dra. Ficticia Editada",
      duracion_default_min: 60,
    });
  });

  it("test_baja_profesional_emite_delete_y_deja_fila_inactiva", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      within(filaDe("Dra. Ficticia Uno")).getByRole("button", {
        name: "Dar de baja",
      }),
    );
    fetchMock.mockResolvedValueOnce(
      json({ ...profesionalA, activo: false }),
    );
    fireEvent.click(
      within(filaDe("Dra. Ficticia Uno")).getByRole("button", {
        name: "Confirmar baja",
      }),
    );

    await waitFor(() => {
      expect(
        within(filaDe("Dra. Ficticia Uno")).getByText("Inactivo"),
      ).toBeDefined();
    });
    const [borrado] = llamadas(fetchMock, "DELETE");
    expect(borrado).toBeDefined();
    expect(borrado?.url).toContain(`/api/profesionales/${PROF_A}`);
    expect(borrado?.url).not.toContain("fisico");
    expect(screen.getByText("Dra. Ficticia Uno")).toBeDefined();
  });

  it("test_reactivar_profesional_emite_put_activo_true", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Inactiva Ficticia");
    fetchMock.mockResolvedValueOnce(
      json({ ...profesionalInactivo, activo: true }),
    );
    fireEvent.click(
      within(filaDe("Dra. Inactiva Ficticia")).getByRole("button", {
        name: "Reactivar",
      }),
    );

    await waitFor(() => {
      expect(
        within(filaDe("Dra. Inactiva Ficticia")).getByText("Activo"),
      ).toBeDefined();
    });
    const [put] = llamadas(fetchMock, "PUT");
    expect(put).toBeDefined();
    expect(put?.url).toContain(`/api/profesionales/${PROF_C}`);
    expect(put?.body).toEqual({ activo: true });
    expect(
      within(filaDe("Dra. Inactiva Ficticia")).getByRole("button", {
        name: "Dar de baja",
      }),
    ).toBeDefined();
  });

  it("test_edicion_profesional_404_cierra_formulario_y_refresca", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Ficticia Uno");
    fireEvent.click(
      within(filaDe("Dra. Ficticia Uno")).getByRole("button", {
        name: "Editar",
      }),
    );
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Dra. Ya No Existe" },
    });

    fetchMock
      .mockResolvedValueOnce(json({ detail: "No encontrado" }, 404))
      .mockResolvedValueOnce(json(pageTodos));

    fireEvent.click(
      screen.getByRole("button", { name: /guardar cambios/i }),
    );

    expect(
      await screen.findByText(/ya no está disponible/i),
    ).toBeDefined();
    expect(screen.queryByRole("form")).toBeNull();
    await waitFor(() => expect(cantGetProfesionales(fetchMock)).toBe(2));
  });

  it("test_fila_inactiva_solo_ofrece_reactivar", async () => {
    const fetchMock = stubFetch();
    sesionYListado(fetchMock, pageTodos);

    renderAdmin();
    await screen.findByText("Dra. Inactiva Ficticia");
    const fila = filaDe("Dra. Inactiva Ficticia");

    expect(
      within(fila).getByRole("button", { name: "Reactivar" }),
    ).toBeDefined();
    expect(
      within(fila).queryByRole("button", { name: "Dar de baja" }),
    ).toBeNull();
    expect(
      within(fila).queryByRole("button", { name: "Editar" }),
    ).toBeNull();
  });
});

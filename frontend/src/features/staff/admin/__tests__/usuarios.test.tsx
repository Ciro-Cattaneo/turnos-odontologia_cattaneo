/**
 * Administración de usuarios staff (capa: integración, router en memoria).
 * Cubre FA listado keyset, alta con invariante de rol, edición sin email ni
 * password, baja/reactivación y guarda de último admin (SA R1–R5).
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

const USR_ADMIN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const USR_RECEPCION = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const USR_ODONTOLOGO = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const PROF_A = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const PROF_B = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";

const usuarioAdmin = {
  id: USR_ADMIN,
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
  activo: true,
};
const usuarioRecepcion = {
  id: USR_RECEPCION,
  email: "recepcion@cattaneo.test",
  rol: "recepcion",
  profesional_id: null,
  activo: true,
};
const usuarioOdontologo = {
  id: USR_ODONTOLOGO,
  email: "odontologo@cattaneo.test",
  rol: "odontologo",
  profesional_id: PROF_B,
  activo: false,
};

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
const profesionalesActivos = {
  items: [profesionalA, profesionalB],
  next_cursor: null,
};

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function urlDe(url: string): URL {
  return new URL(url, "http://test.local");
}

function pathDe(url: string): string {
  return urlDe(url).pathname;
}

type Handler = (
  ruta: string,
  method: string,
  init: RequestInit,
) => Response | undefined;

function stubApi(handler: Handler): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((entrada: unknown, init?: RequestInit) => {
    const ruta = String(entrada);
    const metodo = init?.method ?? "GET";
    const respuesta = handler(ruta, metodo, init ?? {});
    if (respuesta === undefined) {
      throw new Error(`fetch no esperado: ${metodo} ${pathDe(ruta)}`);
    }
    return Promise.resolve(respuesta);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubAdmin(
  usuarios: Handler,
  profesionales: Response = json(profesionalesActivos),
): ReturnType<typeof vi.fn> {
  return stubApi((ruta, method, init) => {
    const path = pathDe(ruta);
    if (path === "/api/auth/me") {
      return json(meAdmin);
    }
    if (path === "/api/profesionales") {
      return profesionales;
    }
    if (path.startsWith("/api/usuarios-staff")) {
      return usuarios(ruta, method, init);
    }
    return undefined;
  });
}

function renderAdmin(): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/admin/usuarios"],
  });
  render(<RouterProvider router={router} />);
  return router;
}

interface Llamada {
  url: string;
  body: unknown;
}

function llamadas(
  fetchMock: ReturnType<typeof vi.fn>,
  method: string,
  path: string,
): Llamada[] {
  const encontradas: Llamada[] = [];
  for (const call of fetchMock.mock.calls) {
    const url = String(call[0]);
    const init = (call[1] ?? {}) as RequestInit;
    const metodo = init.method ?? "GET";
    if (metodo === method && pathDe(url) === path) {
      encontradas.push({
        url,
        body:
          typeof init.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      });
    }
  }
  return encontradas;
}

function filaDe(email: string): HTMLElement {
  const encabezado = screen.getByRole("heading", {
    level: 2,
    name: email,
  });
  const fila = encabezado.closest("li");
  if (fila === null) {
    throw new Error(`No se encontró la fila de ${email}`);
  }
  return fila;
}

function abrirAlta(): void {
  fireEvent.click(screen.getByRole("button", { name: /agregar usuario/i }));
}

function completarAlta(email: string, password: string): void {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("Contraseña"), {
    target: { value: password },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("usuarios staff admin: listado keyset", () => {
  it("test_usuarios_primera_pagina_pide_limit_20", async () => {
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method !== "GET") {
        return undefined;
      }
      return json({
        items: [usuarioAdmin, usuarioRecepcion],
        next_cursor: null,
      });
    });

    renderAdmin();

    expect(await screen.findByText("admin@cattaneo.test")).toBeDefined();
    const listados = llamadas(fetchMock, "GET", "/api/usuarios-staff");
    expect(listados).toHaveLength(1);
    expect(urlDe(listados[0]?.url ?? "").searchParams.get("limit")).toBe("20");
    expect(
      urlDe(listados[0]?.url ?? "").searchParams.has("cursor"),
    ).toBe(false);
  });

  it("test_usuarios_cargar_mas_usa_next_cursor_sin_duplicar", async () => {
    let pagina = 0;
    const fetchMock = stubAdmin((ruta, method) => {
      if (method !== "GET") {
        return undefined;
      }
      const cursor = urlDe(ruta).searchParams.get("cursor");
      pagina += 1;
      if (cursor === null) {
        return json({
          items: [usuarioAdmin, usuarioRecepcion],
          next_cursor: "cursor-usuarios-2",
        });
      }
      return json({
        items: [usuarioRecepcion, usuarioOdontologo],
        next_cursor: null,
      });
    });

    renderAdmin();
    await screen.findByText("admin@cattaneo.test");
    fireEvent.click(
      await screen.findByRole("button", { name: /cargar más/i }),
    );

    await waitFor(() =>
      expect(screen.getAllByRole("listitem")).toHaveLength(3),
    );
    expect(
      screen.getByText("odontologo@cattaneo.test"),
    ).toBeDefined();
    expect(screen.getAllByText("recepcion@cattaneo.test")).toHaveLength(1);
    const listados = llamadas(fetchMock, "GET", "/api/usuarios-staff");
    expect(listados).toHaveLength(2);
    expect(
      urlDe(listados[1]?.url ?? "").searchParams.get("cursor"),
    ).toBe("cursor-usuarios-2");
    expect(pagina).toBe(2);
  });
});

describe("usuarios staff admin: alta", () => {
  it("test_alta_usuario_odontologo_sin_profesional_no_emite_post", async () => {
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioAdmin], next_cursor: null });
      }
      return undefined;
    });
    renderAdmin();
    await screen.findByText("admin@cattaneo.test");
    abrirAlta();
    completarAlta("nuevo.odontologo@cattaneo.test", "password-ficticia");
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "odontologo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /crear usuario/i }));

    expect(llamadas(fetchMock, "POST", "/api/usuarios-staff")).toHaveLength(0);
    const selector = screen.getByLabelText("Profesional");
    await waitFor(() =>
      expect(selector.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(screen.getByText(/elegí un profesional activo/i)).toBeDefined();
    expect(screen.getByText(/solo se ofrecen profesionales activos/i)).toBeDefined();
  });

  it("test_alta_usuario_cambiar_a_recepcion_oculta_y_limpia_profesional_id", async () => {
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioAdmin], next_cursor: null });
      }
      return json(usuarioRecepcion, 201);
    });

    renderAdmin();
    await screen.findByText("admin@cattaneo.test");
    abrirAlta();
    completarAlta("nuevo@cattaneo.test", "password-ficticia");
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "odontologo" },
    });
    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_A },
    });
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "recepcion" },
    });

    expect(screen.queryByLabelText("Profesional")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /crear usuario/i }));

    await waitFor(() =>
      expect(llamadas(fetchMock, "POST", "/api/usuarios-staff")).toHaveLength(1),
    );
    const [post] = llamadas(fetchMock, "POST", "/api/usuarios-staff");
    const body = post?.body as Record<string, unknown>;
    expect(body["rol"]).toBe("recepcion");
    expect("profesional_id" in body).toBe(false);
  });

  it("test_alta_usuario_409_email_duplicado_menciona_reactivar", async () => {
    stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioAdmin], next_cursor: null });
      }
      return json({ detail: { codigo: "email_duplicado" } }, 409);
    });

    renderAdmin();
    await screen.findByText("admin@cattaneo.test");
    abrirAlta();
    completarAlta("tomado@cattaneo.test", "password-ficticia");
    fireEvent.click(screen.getByRole("button", { name: /crear usuario/i }));

    expect(await screen.findByText(/reactivá la fila existente/i)).toBeDefined();
    expect(screen.queryByText(/usuario creado/i)).toBeNull();
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
      "tomado@cattaneo.test",
    );
    expect((screen.getByLabelText("Rol") as HTMLSelectElement).value).toBe(
      "recepcion",
    );
  });

  it("test_alta_usuario_400_profesional_id_marca_solo_ese_campo", async () => {
    stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioAdmin], next_cursor: null });
      }
      return json(
        {
          detail: [
            {
              campo: "profesional_id",
              error: "el profesional no existe o está inactivo",
              tipo: "value_error",
            },
          ],
        },
        400,
      );
    });

    renderAdmin();
    await screen.findByText("admin@cattaneo.test");
    abrirAlta();
    completarAlta("nuevo@cattaneo.test", "password-ficticia");
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "odontologo" },
    });
    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_A },
    });
    fireEvent.click(screen.getByRole("button", { name: /crear usuario/i }));

    const selector = screen.getByLabelText("Profesional");
    await waitFor(() =>
      expect(selector.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(selector.getAttribute("aria-describedby")).not.toBeNull();
    expect(
      screen.getByLabelText("Email").getAttribute("aria-invalid"),
    ).not.toBe("true");
    expect(screen.queryByText(/usuario creado/i)).toBeNull();
  });
});

describe("usuarios staff admin: edición y baja", () => {
  it("test_edicion_usuario_envia_solo_rol_y_profesional_id", async () => {
    const actualizado = {
      ...usuarioRecepcion,
      rol: "odontologo",
      profesional_id: PROF_B,
    };
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioRecepcion], next_cursor: null });
      }
      return json(actualizado);
    });

    renderAdmin();
    await screen.findByText("recepcion@cattaneo.test");
    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Editar",
      }),
    );
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "odontologo" },
    });
    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_B },
    });
    fireEvent.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(
      await screen.findByText(/usuario actualizado/i),
    ).toBeDefined();
    const [put] = llamadas(fetchMock, "PUT", `/api/usuarios-staff/${USR_RECEPCION}`);
    expect(put?.body).toEqual({
      rol: "odontologo",
      profesional_id: PROF_B,
    });
    expect(screen.getByText(/Rol: Odontólogo/)).toBeDefined();
    expect(screen.getByText(/Profesional: Dr\. Ficticio Dos/)).toBeDefined();
  });

  it("test_edicion_usuario_no_ofrece_inputs_de_email_ni_password", async () => {
    stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioRecepcion], next_cursor: null });
      }
      return json(usuarioRecepcion);
    });

    renderAdmin();
    await screen.findByText("recepcion@cattaneo.test");
    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Editar",
      }),
    );

    expect(screen.queryByLabelText("Email")).toBeNull();
    expect(screen.queryByLabelText("Contraseña")).toBeNull();
    expect(document.querySelector('input[name="email"]')).toBeNull();
    expect(document.querySelector('input[name="password"]')).toBeNull();
    const formulario = screen.getByRole("form", {
      name: /editar usuario staff/i,
    });
    expect(
      within(formulario).getByText(/recepcion@cattaneo\.test/),
    ).toBeDefined();
  });

  it.each([
    ["test_edicion_usuario_422_ultimo_admin_no_marca_exito", "edicion"],
    ["test_baja_usuario_422_ultimo_admin_conserva_la_fila", "baja"],
  ] as const)(
    "%s",
    async (_nombre, accion) => {
      stubAdmin((_ruta, method) => {
        if (method === "GET") {
          return json({ items: [usuarioAdmin], next_cursor: null });
        }
        return json(
          {
            detail: {
              codigo: "ultimo_admin",
              mensaje: "No se puede dejar el sistema sin admin activo",
            },
          },
          422,
        );
      });

      renderAdmin();
      await screen.findByText("admin@cattaneo.test");

      if (accion === "edicion") {
        fireEvent.click(
          within(filaDe("admin@cattaneo.test")).getByRole("button", {
            name: "Editar",
          }),
        );
        fireEvent.click(screen.getByLabelText("Activo"));
        fireEvent.click(
          screen.getByRole("button", { name: /guardar cambios/i }),
        );
      } else {
        fireEvent.click(
          within(filaDe("admin@cattaneo.test")).getByRole("button", {
            name: "Dar de baja",
          }),
        );
        fireEvent.click(
          within(filaDe("admin@cattaneo.test")).getByRole("button", {
            name: "Confirmar baja",
          }),
        );
      }

      expect(
        await screen.findByText(/al menos un admin activo/i),
      ).toBeDefined();
      expect(screen.queryByText(/usuario (creado|actualizado)/i)).toBeNull();
      expect(screen.queryByText(/usuario dado de baja/i)).toBeNull();
      expect(
        within(filaDe("admin@cattaneo.test")).getByText("Activo"),
      ).toBeDefined();
    },
  );

  it("test_baja_y_reactivacion_usuario_actualizan_etiqueta_sin_recarga", async () => {
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioRecepcion], next_cursor: null });
      }
      if (method === "DELETE") {
        return json({ ...usuarioRecepcion, activo: false });
      }
      return json({ ...usuarioRecepcion, activo: true });
    });

    renderAdmin();
    await screen.findByText("recepcion@cattaneo.test");
    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Dar de baja",
      }),
    );
    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Confirmar baja",
      }),
    );

    await waitFor(() =>
      expect(
        within(filaDe("recepcion@cattaneo.test")).getByText("Inactivo"),
      ).toBeDefined(),
    );
    expect(
      llamadas(fetchMock, "GET", "/api/usuarios-staff"),
    ).toHaveLength(1);

    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Reactivar",
      }),
    );

    await waitFor(() =>
      expect(
        within(filaDe("recepcion@cattaneo.test")).getByText("Activo"),
      ).toBeDefined(),
    );
    const [baja] = llamadas(
      fetchMock,
      "DELETE",
      `/api/usuarios-staff/${USR_RECEPCION}`,
    );
    expect(baja).toBeDefined();
    const [reactivacion] = llamadas(
      fetchMock,
      "PUT",
      `/api/usuarios-staff/${USR_RECEPCION}`,
    );
    expect(reactivacion?.body).toEqual({ activo: true });
    expect(
      llamadas(fetchMock, "GET", "/api/usuarios-staff"),
    ).toHaveLength(1);
  });

  it("test_edicion_usuario_404_cierra_formulario_y_refresca", async () => {
    const fetchMock = stubAdmin((_ruta, method) => {
      if (method === "GET") {
        return json({ items: [usuarioRecepcion], next_cursor: null });
      }
      return json({ detail: "No encontrado" }, 404);
    });

    renderAdmin();
    await screen.findByText("recepcion@cattaneo.test");
    fireEvent.click(
      within(filaDe("recepcion@cattaneo.test")).getByRole("button", {
        name: "Editar",
      }),
    );
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(await screen.findByText(/ya no está disponible/i)).toBeDefined();
    expect(screen.queryByRole("form")).toBeNull();
    await waitFor(() =>
      expect(
        llamadas(fetchMock, "GET", "/api/usuarios-staff"),
      ).toHaveLength(2),
    );
  });
});

/**
 * §10.3 — a11y de formularios y paneles staff: labels asociados, `aria-invalid`
 * + `aria-describedby`, `role="alert"` y foco al primer error tras un submit
 * inválido. Capa: integración (router en memoria, fetch stubbeado en el borde).
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

import { appRoutes } from "../../../App";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const HOY = "2026-11-13";
const AHORA = "2026-11-13T12:00:00Z";

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

const PROFESIONALES_PAGE = { items: [profesionalA], next_cursor: null };
const TURNO_ID = "turno-ficticio-a11y";

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

function renderRuta(ruta: string): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, { initialEntries: [ruta] });
  render(<RouterProvider router={router} />);
  return router;
}

function agendaPayload(franjas: unknown[]): unknown {
  return {
    profesional_id: ID_A,
    vista: "dia",
    dias: [{ fecha: HOY, franjas }],
    next_cursor: "2026-11-14",
    ultima_actualizacion: null,
  };
}

function franjaLibre(inicio = "09:00", fin = "09:30"): unknown {
  return {
    tipo: "libre",
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
  };
}

function franjaOcupada(inicio = "10:00", fin = "10:30"): unknown {
  return {
    tipo: "ocupado",
    turno_id: TURNO_ID,
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
    estado: "confirmado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

interface FichaParams {
  inicio?: string;
  fin?: string;
  estado?: string;
}

function fichaPayload(params: FichaParams = {}): unknown {
  return {
    id: TURNO_ID,
    estado: params.estado ?? "confirmado",
    origen: "recepcion",
    inicio: params.inicio ?? `${HOY}T10:00:00-03:00`,
    fin: params.fin ?? `${HOY}T10:30:00-03:00`,
    duracion_min: 30,
    profesional: {
      id: ID_A,
      nombre: "Dra. Alpha Ficticia",
      especialidad: "Clínica",
    },
    paciente: {
      id: "paciente-ficticio-1",
      nombre: "Paciente Ficticio",
      dni: "12345678",
      telefono: "1145550000",
      obra_social: "OS Ficticia",
      email: "paciente@ficticio.test",
      activo: true,
    },
    auditoria: { items: [], next_cursor: null },
  };
}

interface Mutacion {
  url: string;
  method: string;
  body: unknown;
}

function mutaciones(
  mock: ReturnType<typeof vi.fn>,
  method: string,
): Mutacion[] {
  const encontradas: Mutacion[] = [];
  for (const call of mock.mock.calls) {
    const url: unknown = call[0];
    const init: RequestInit | undefined = call[1] as RequestInit | undefined;
    if (typeof url === "string" && init?.method === method) {
      const crudo = typeof init.body === "string" ? init.body : "null";
      encontradas.push({ url, method, body: JSON.parse(crudo) as unknown });
    }
  }
  return encontradas;
}

async function abrirFicha(
  fetchMock: ReturnType<typeof vi.fn>,
  franjas: unknown[],
  ficha: unknown,
  hora: string,
): Promise<HTMLElement> {
  fetchMock
    .mockResolvedValueOnce(json(meRecepcion))
    .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
    .mockResolvedValueOnce(json(agendaPayload(franjas)))
    .mockResolvedValueOnce(json(ficha));
  renderRuta("/staff/agenda");
  const boton = await screen.findByRole("button", {
    name: `Ver detalle del turno de las ${hora}`,
  });
  fireEvent.click(boton);
  return screen.findByRole("region", { name: /detalle del turno/i });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("a11y de formularios staff", () => {
  it("test_login_400_asocia_label_marca_aria_y_enfoca_el_campo", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "email",
              error: "El email no tiene un formato válido.",
              tipo: "email_invalido",
            },
          ],
        },
        400,
      ),
    );

    renderRuta("/staff/login");
    const email = screen.getByLabelText("Email");
    expect(screen.getByLabelText("Contraseña")).toBeDefined();

    fireEvent.change(email, { target: { value: "sin-arroba" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    await waitFor(() =>
      expect(email.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(email.getAttribute("aria-describedby")).toBe("email-error");
    const mensaje = document.getElementById("email-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(mensaje?.textContent).toContain("formato válido");
    await waitFor(() => expect(document.activeElement).toBe(email));
  });

  it("test_alta_con_campos_vacios_marca_aria_y_enfoca_el_primer_error", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(agendaPayload([franjaLibre()])));

    renderRuta("/staff/agenda");
    await screen.findByText("Libre");
    fireEvent.click(
      screen.getByRole("button", { name: /crear turno de las 09:00/i }),
    );
    const form = await screen.findByRole("form", { name: /alta de turno/i });
    for (const etiqueta of [
      "Nombre y apellido",
      "DNI",
      "Teléfono",
      "Obra social",
      "Email",
    ]) {
      expect(within(form).getByLabelText(etiqueta)).toBeDefined();
    }

    fireEvent.click(
      within(form).getByRole("button", { name: /confirmar alta/i }),
    );

    const nombre = within(form).getByLabelText("Nombre y apellido");
    await waitFor(() =>
      expect(nombre.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(nombre.getAttribute("aria-describedby")).toBe("alta-nombre-error");
    const mensaje = document.getElementById("alta-nombre-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(document.activeElement).toBe(nombre);
  });

  it("test_correccion_400_marca_aria_y_enfoca_el_campo", async () => {
    const fetchMock = stubFetch();
    const panel = await abrirFicha(
      fetchMock,
      [franjaOcupada()],
      fichaPayload(),
      "10:00",
    );
    fireEvent.click(
      within(panel).getByRole("button", {
        name: /corregir datos del paciente/i,
      }),
    );
    const form = await within(panel).findByRole("form", {
      name: /corregir datos del paciente/i,
    });
    const dni = within(form).getByLabelText("DNI");

    fireEvent.change(dni, { target: { value: "12" } });
    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "dni",
              error: "`dni` debe tener 7 u 8 dígitos",
              tipo: "dni_formato",
            },
          ],
        },
        400,
      ),
    );
    fireEvent.click(
      within(form).getByRole("button", { name: /guardar corrección/i }),
    );

    await waitFor(() => expect(dni.getAttribute("aria-invalid")).toBe("true"));
    expect(dni.getAttribute("aria-describedby")).toBe("corregir-dni-error");
    const mensaje = document.getElementById("corregir-dni-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    expect(mensaje?.textContent).toContain("7 u 8 dígitos");
    await waitFor(() => expect(document.activeElement).toBe(dni));
    expect(mutaciones(fetchMock, "PUT")).toHaveLength(1);
  });

  it("test_cancelacion_422_motivo_enfoca_y_anuncia_el_campo", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    const panel = await abrirFicha(
      fetchMock,
      [franjaOcupada("14:00", "14:30")],
      fichaPayload({
        inicio: `${HOY}T14:00:00-03:00`,
        fin: `${HOY}T14:30:00-03:00`,
      }),
      "14:00",
    );
    fireEvent.click(
      within(panel).getByRole("button", { name: /cancelar turno/i }),
    );
    const form = await within(panel).findByRole("form", {
      name: /cancelar turno/i,
    });
    expect(within(form).queryByLabelText(/motivo/i)).toBeNull();

    fetchMock.mockResolvedValueOnce(
      json({ detail: { codigo: "motivo_requerido" } }, 422),
    );
    fireEvent.click(
      within(form).getByRole("button", { name: /confirmar cancelación/i }),
    );

    const motivo = await within(form).findByLabelText(/motivo/i);
    await waitFor(() => expect(motivo.getAttribute("aria-invalid")).toBe("true"));
    expect(motivo.getAttribute("aria-required")).toBe("true");
    expect(motivo.getAttribute("aria-describedby")).toBe(
      "cancelar-motivo-error",
    );
    const mensaje = document.getElementById("cancelar-motivo-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    await waitFor(() => expect(document.activeElement).toBe(motivo));
    expect(mutaciones(fetchMock, "DELETE")).toHaveLength(1);
  });

  it("test_reprogramacion_400_marca_inicio_y_enfoca_el_campo", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    const panel = await abrirFicha(
      fetchMock,
      [franjaOcupada()],
      fichaPayload(),
      "10:00",
    );
    fetchMock.mockResolvedValueOnce(
      json(agendaPayload([franjaLibre("14:00", "14:30")])),
    );
    fireEvent.click(
      within(panel).getByRole("button", { name: /reprogramar turno/i }),
    );
    const form = await within(panel).findByRole("form", {
      name: /reprogramar turno/i,
    });

    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "inicio",
              error: "`inicio` debe ser una fecha futura",
              tipo: "value_error",
            },
          ],
        },
        400,
      ),
    );
    fireEvent.click(
      within(form).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    const inicio = within(form).getByLabelText(/horario destino/i);
    await waitFor(() => expect(inicio.getAttribute("aria-invalid")).toBe("true"));
    expect(inicio.getAttribute("aria-describedby")).toBe("repro-inicio-error");
    const mensaje = document.getElementById("repro-inicio-error");
    expect(mensaje?.getAttribute("role")).toBe("alert");
    await waitFor(() => expect(document.activeElement).toBe(inicio));
    expect(mutaciones(fetchMock, "PUT")).toHaveLength(1);
  });
});

describe("a11y de paneles staff", () => {
  it("test_panel_de_ficha_e_historial_son_regiones_etiquetadas_con_foco", async () => {
    const fetchMock = stubFetch();
    const panel = await abrirFicha(
      fetchMock,
      [franjaOcupada()],
      fichaPayload(),
      "10:00",
    );

    const historial = within(panel).getByRole("region", {
      name: /historial del turno/i,
    });
    expect(historial).toBeDefined();
    expect(
      within(historial).getByText(/sin movimientos registrados/i),
    ).toBeDefined();

    const titulo = within(panel).getByRole("heading", {
      name: /detalle del turno/i,
    });
    expect(titulo.getAttribute("tabindex")).toBe("-1");
    await waitFor(() => expect(document.activeElement).toBe(titulo));
  });

  it("test_panel_de_fallidas_es_una_region_con_lista_accesible", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({
          items: [
            {
              id: "fallida-ficticia-1",
              turno_id: TURNO_ID,
              tipo: "recordatorio",
              intentos: 3,
              error: "SMTP no disponible",
              enviar_en: `${HOY}T09:00:00Z`,
              paciente_nombre: "Paciente Ficticio",
              paciente_email: "paciente@ficticio.test",
              inicio: `${HOY}T10:00:00-03:00`,
              fin: `${HOY}T10:30:00-03:00`,
            },
          ],
          next_cursor: null,
        }),
      );

    renderRuta("/staff/notificaciones");
    const region = await screen.findByRole("region", {
      name: "Notificaciones fallidas",
    });
    const lista = within(region).getByRole("list", {
      name: /notificaciones fallidas/i,
    });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(1);
    expect(within(region).getByText(/recordatorio/i)).toBeDefined();
  });
});

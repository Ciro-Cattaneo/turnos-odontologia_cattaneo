/**
 * §10.5 — privacidad en la capa staff: los datos del paciente usados en la
 * ficha, el alta, la reprogramación, la cancelación y la corrección nunca se
 * reflejan en la URL ni en las URLs de `fetch` (Ley 25.326).
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const HOY = "2026-11-13";
const TURNO_ID = "turno-ficticio-privacidad";

const NOMBRE_FICHA = "Nombre Reservado Ficticio";
const DNI_FICHA = "30111222";
const TELEFONO_FICHA = "1140001111";
const OBRA_FICHA = "Obra Reservada Ficticia";
const EMAIL_FICHA = "reservado@ficticio.test";

const NOMBRE_ALTA = "Nombre Nuevo Ficticio";
const DNI_ALTA = "30999888";
const TELEFONO_ALTA = "1140009999";
const OBRA_ALTA = "Obra Nueva Ficticia";
const EMAIL_ALTA = "nuevo@ficticio.test";

const DATOS_FICHA = [
  NOMBRE_FICHA,
  DNI_FICHA,
  TELEFONO_FICHA,
  OBRA_FICHA,
  EMAIL_FICHA,
];

const DATOS_ALTA = [
  NOMBRE_ALTA,
  DNI_ALTA,
  TELEFONO_ALTA,
  OBRA_ALTA,
  EMAIL_ALTA,
];

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

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
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
    paciente: { id: "paciente-ficticio-1", nombre: NOMBRE_FICHA },
  };
}

function fichaPayload(): unknown {
  return {
    id: TURNO_ID,
    estado: "confirmado",
    origen: "recepcion",
    inicio: `${HOY}T10:00:00-03:00`,
    fin: `${HOY}T10:30:00-03:00`,
    duracion_min: 30,
    profesional: {
      id: ID_A,
      nombre: "Dra. Alpha Ficticia",
      especialidad: "Clínica",
    },
    paciente: {
      id: "paciente-ficticio-1",
      nombre: NOMBRE_FICHA,
      dni: DNI_FICHA,
      telefono: TELEFONO_FICHA,
      obra_social: OBRA_FICHA,
      email: EMAIL_FICHA,
      activo: true,
    },
    auditoria: { items: [], next_cursor: null },
  };
}

const TURNO_OUT = {
  id: "turno-ficticio-nuevo",
  estado: "confirmado",
  inicio: `${HOY}T09:00:00-03:00`,
  fin: `${HOY}T09:30:00-03:00`,
  duracion_min: 30,
  notificaciones_encoladas: true,
};

const CORRECCION_OUT = {
  id: TURNO_ID,
  paciente: {
    id: "paciente-ficticio-1",
    nombre: NOMBRE_FICHA,
    dni: DNI_FICHA,
    telefono: TELEFONO_FICHA,
    obra_social: OBRA_FICHA,
    email: EMAIL_FICHA,
    activo: true,
  },
  notificaciones_encoladas: true,
};

function stubApi(): ReturnType<typeof vi.fn> {
  const ficha = fichaPayload();
  const fetchMock = vi.fn(
    (entrada: unknown, init?: RequestInit): Promise<Response> => {
      const url = typeof entrada === "string" ? entrada : String(entrada);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/auth/me")) {
        return Promise.resolve(json(meRecepcion));
      }
      if (
        url.endsWith("/api/profesionales") ||
        url.includes("/api/profesionales?")
      ) {
        return Promise.resolve(json(PROFESIONALES_PAGE));
      }
      if (url.includes("/agenda?")) {
        return Promise.resolve(
          json(agendaPayload([franjaLibre(), franjaOcupada()])),
        );
      }
      if (method === "POST" && url === "/api/turnos") {
        return Promise.resolve(json(TURNO_OUT, 201));
      }
      if (method === "PUT" && url.endsWith("/paciente")) {
        return Promise.resolve(json(CORRECCION_OUT));
      }
      if (method === "PUT") {
        return Promise.resolve(json(TURNO_OUT));
      }
      if (method === "DELETE") {
        return Promise.resolve(
          json({
            id: TURNO_ID,
            estado: "cancelado",
            inicio: `${HOY}T10:00:00-03:00`,
            fin: `${HOY}T10:30:00-03:00`,
            duracion_min: 30,
            notificaciones_encoladas: true,
            mensaje: "Turno cancelado.",
          }),
        );
      }
      if (method === "GET" && url.startsWith("/api/turnos/")) {
        return Promise.resolve(json(ficha));
      }
      return Promise.reject(new Error(`fetch no esperado: ${method} ${url}`));
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderRuta(): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/agenda"],
  });
  render(<RouterProvider router={router} />);
  return router;
}

function urlActual(router: ReturnType<typeof createMemoryRouter>): string {
  const { pathname, search, hash } = router.state.location;
  return `${pathname}${search}${hash}`;
}

function expectUrlSinDatos(
  router: ReturnType<typeof createMemoryRouter>,
  datos: string[],
): void {
  const url = urlActual(router);
  expect(url).toBe("/staff/agenda");
  for (const dato of datos) {
    expect(url).not.toContain(dato);
    expect(url).not.toContain(encodeURIComponent(dato));
  }
}

function urlsLlamadas(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map((call) => String(call[0]));
}

function expectFetchSinDatos(
  fetchMock: ReturnType<typeof vi.fn>,
  datos: string[],
): void {
  const urls = urlsLlamadas(fetchMock);
  expect(urls.length).toBeGreaterThan(0);
  for (const url of urls) {
    for (const dato of datos) {
      expect(url).not.toContain(dato);
      expect(url).not.toContain(encodeURIComponent(dato));
    }
  }
}

async function abrirFicha(): Promise<HTMLElement> {
  const boton = await screen.findByRole("button", {
    name: "Ver detalle del turno de las 10:00",
  });
  fireEvent.click(boton);
  return screen.findByRole("region", { name: /detalle del turno/i });
}

function completarAlta(form: HTMLElement): void {
  const valores: Array<[string, string]> = [
    ["Nombre y apellido", NOMBRE_ALTA],
    ["DNI", DNI_ALTA],
    ["Teléfono", TELEFONO_ALTA],
    ["Obra social", OBRA_ALTA],
    ["Email", EMAIL_ALTA],
  ];
  for (const [etiqueta, valor] of valores) {
    fireEvent.change(within(form).getByLabelText(etiqueta), {
      target: { value: valor },
    });
  }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("privacidad de datos del paciente en staff", () => {
  it("test_ficha_y_alta_no_filtran_datos_a_la_url_ni_al_fetch", async () => {
    const fetchMock = stubApi();
    const router = renderRuta();
    await screen.findByText("Libre");

    const panel = await abrirFicha();
    expect(within(panel).getByText(NOMBRE_FICHA)).toBeDefined();
    expectUrlSinDatos(router, DATOS_FICHA);

    fireEvent.click(
      screen.getByRole("button", { name: /crear turno de las 09:00/i }),
    );
    const form = await screen.findByRole("form", { name: /alta de turno/i });
    completarAlta(form);
    fireEvent.click(
      within(form).getByRole("button", { name: /confirmar alta/i }),
    );
    await screen.findByText(/turno creado/i, { exact: false });

    expectUrlSinDatos(router, [...DATOS_FICHA, ...DATOS_ALTA]);
    expectFetchSinDatos(fetchMock, [...DATOS_FICHA, ...DATOS_ALTA]);
    const posteos = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(posteos).toHaveLength(1);
    expect(String(posteos[0]?.[0])).toBe("/api/turnos");
  });

  it("test_reprogramar_cancelar_y_corregir_no_filtran_datos_a_la_url", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(`${HOY}T07:00:00-03:00`));

    const fetchMock = stubApi();
    const router = renderRuta();
    await screen.findByText("Libre");

    const panel = await abrirFicha();

    fireEvent.click(
      within(panel).getByRole("button", { name: /reprogramar turno/i }),
    );
    const repro = await within(panel).findByRole("form", {
      name: /reprogramar turno/i,
    });
    fireEvent.click(
      within(repro).getByRole("button", { name: /confirmar reprogramación/i }),
    );
    await within(panel).findByText("Turno reprogramado.");

    fireEvent.click(
      within(panel).getByRole("button", { name: /cancelar turno/i }),
    );
    const cancel = await within(panel).findByRole("form", {
      name: /cancelar turno/i,
    });
    fireEvent.click(
      within(cancel).getByRole("button", { name: /confirmar cancelación/i }),
    );
    await within(panel).findByText("Turno cancelado.");

    fireEvent.click(
      within(panel).getByRole("button", {
        name: /corregir datos del paciente/i,
      }),
    );
    const correccion = await within(panel).findByRole("form", {
      name: /corregir datos del paciente/i,
    });
    fireEvent.click(
      within(correccion).getByRole("button", { name: /guardar corrección/i }),
    );
    await within(panel).findByText("Datos del paciente corregidos.");

    expectUrlSinDatos(router, DATOS_FICHA);
    expectFetchSinDatos(fetchMock, DATOS_FICHA);
    const metodos = fetchMock.mock.calls.map(
      (call) => (call[1] as RequestInit | undefined)?.method ?? "GET",
    );
    expect(metodos).toContain("PUT");
    expect(metodos).toContain("DELETE");
  });

  it("test_recarga_de_la_agenda_mantiene_la_url_sin_datos", async () => {
    const fetchMock = stubApi();
    const router = renderRuta();
    await screen.findByText("Libre");
    await abrirFicha();
    expectUrlSinDatos(router, DATOS_FICHA);

    cleanup();

    const fetchRecarga = stubApi();
    const routerRecarga = renderRuta();
    await screen.findByText("Libre", undefined, { timeout: 3000 });

    expectUrlSinDatos(routerRecarga, DATOS_FICHA);
    expectFetchSinDatos(fetchRecarga, DATOS_FICHA);
    expect(urlsLlamadas(fetchRecarga).length).toBeGreaterThan(0);
    expect(urlsLlamadas(fetchMock).length).toBeGreaterThan(0);
  });
});

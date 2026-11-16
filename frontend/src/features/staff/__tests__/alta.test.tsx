/**
 * Ficha de turno y alta de recepción (§6.1–§6.4): panel en estado sin URL,
 * alta con los cinco datos, 409 con alternativos, 201 sin mails y RBAC.
 * Capa: integración (router en memoria, fetch stubbeado en el borde).
 * # AC frontend-agenda-staff/Alta de turno de recepción y privacidad.
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
import { addDias, hoyEnConsultorio } from "../../../shared/format";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const ID_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const HOY = hoyEnConsultorio();

type Rol = "recepcion" | "odontologo" | "admin";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const meAdmin = {
  email: "admin@ficticio.test",
  rol: "admin",
  profesional_id: null,
};
const meOdontologo = {
  email: "odontologo@ficticio.test",
  rol: "odontologo",
  profesional_id: ID_B,
};

function mePorRol(rol: Rol): unknown {
  if (rol === "admin") {
    return meAdmin;
  }
  return rol === "odontologo" ? meOdontologo : meRecepcion;
}

function profesional(id: string, nombre: string, duracion: number): unknown {
  return {
    id,
    nombre,
    especialidad: "Clínica",
    matricula: null,
    duracion_default_min: duracion,
    ultima_actualizacion: null,
  };
}

const profesionalA = profesional(ID_A, "Dra. Alpha Ficticia", 30);
const profesionalB = profesional(ID_B, "Dr. Beta Ficticio", 45);

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

function renderAgenda(): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/agenda"],
  });
  render(<RouterProvider router={router} />);
  return router;
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

interface Posteo {
  url: string;
  body: unknown;
}

function posteos(mock: ReturnType<typeof vi.fn>): Posteo[] {
  const encontrados: Posteo[] = [];
  for (const call of mock.mock.calls) {
    const url: unknown = call[0];
    const init: RequestInit | undefined = call[1] as RequestInit | undefined;
    if (
      typeof url === "string" &&
      rutaDe(url) === "/api/turnos" &&
      init?.method === "POST"
    ) {
      const crudo = typeof init.body === "string" ? init.body : "{}";
      encontrados.push({ url, body: JSON.parse(crudo) as unknown });
    }
  }
  return encontrados;
}

function franjaLibre(
  fecha: string = HOY,
  inicio = "09:00",
  fin = "09:30",
): unknown {
  return {
    tipo: "libre",
    inicio: `${fecha}T${inicio}:00-03:00`,
    fin: `${fecha}T${fin}:00-03:00`,
    duracion_min: 30,
  };
}

function franjaOcupada(fecha: string = HOY): unknown {
  return {
    tipo: "ocupado",
    turno_id: "turno-ocupado-ficticio",
    inicio: `${fecha}T10:00:00-03:00`,
    fin: `${fecha}T10:30:00-03:00`,
    duracion_min: 30,
    estado: "confirmado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

function franjaCerrada(fecha: string = HOY): unknown {
  return {
    tipo: "cerrado",
    turno_id: "turno-cerrado-ficticio",
    inicio: `${fecha}T08:00:00-03:00`,
    fin: `${fecha}T08:30:00-03:00`,
    duracion_min: 30,
    estado: "cancelado",
    paciente: { id: "paciente-ficticio-2", nombre: "Paciente Cerrado" },
  };
}

function agendaPayload(params: {
  profesionalId: string;
  fecha?: string;
  franjas: unknown[];
}): unknown {
  const fecha = params.fecha ?? HOY;
  return {
    profesional_id: params.profesionalId,
    vista: "dia",
    dias: [{ fecha, franjas: params.franjas }],
    next_cursor: addDias(fecha, 1),
    ultima_actualizacion: null,
  };
}

function fichaPayload(params: {
  id: string;
  inicio: string;
  fin: string;
  estado?: string;
  origen?: string;
}): unknown {
  return {
    id: params.id,
    estado: params.estado ?? "confirmado",
    origen: params.origen ?? "recepcion",
    inicio: params.inicio,
    fin: params.fin,
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

function turnoCreado(notificacionesEncoladas: boolean): unknown {
  return {
    id: "turno-nuevo-ficticio",
    estado: "reservado",
    inicio: `${HOY}T09:00:00-03:00`,
    fin: `${HOY}T09:30:00-03:00`,
    duracion_min: 30,
    notificaciones_encoladas: notificacionesEncoladas,
  };
}

const FRANJA_LIBRE_PAYLOAD = agendaPayload({
  profesionalId: ID_A,
  franjas: [franjaLibre()],
});
const PROFESIONALES_PAGE = { items: [profesionalA], next_cursor: null };

async function abrirAlta(): Promise<void> {
  await screen.findByText("Libre");
  fireEvent.click(
    screen.getByRole("button", { name: /crear turno de las 09:00/i }),
  );
  await screen.findByRole("form", { name: /alta de turno/i });
}

function completarPaciente(): void {
  fireEvent.change(screen.getByLabelText("Nombre y apellido"), {
    target: { value: "Paciente Nuevo" },
  });
  fireEvent.change(screen.getByLabelText("DNI"), {
    target: { value: "12345678" },
  });
  fireEvent.change(screen.getByLabelText("Teléfono"), {
    target: { value: "1145550000" },
  });
  fireEvent.change(screen.getByLabelText("Obra social"), {
    target: { value: "OS Ficticia" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "paciente.nuevo@ficticio.test" },
  });
}

function enviarAlta(): void {
  fireEvent.click(screen.getByRole("button", { name: /confirmar alta/i }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

interface CasoDetalle {
  tipo: string;
  hora: string;
  turnoId: string;
  franja: () => unknown;
}

const casosDetalle: CasoDetalle[] = [
  {
    tipo: "ocupado",
    hora: "10:00",
    turnoId: "turno-ocupado-ficticio",
    franja: franjaOcupada,
  },
  {
    tipo: "cerrado",
    hora: "08:00",
    turnoId: "turno-cerrado-ficticio",
    franja: franjaCerrada,
  },
];

describe("detalle de turno", () => {
  it.each(casosDetalle.map((caso) => [caso.tipo, caso] as const))(
    "test_abrir_detalle_desde_franja_%s_no_cambia_la_location",
    async (_tipo, caso) => {
      const fetchMock = stubFetch();
      const franja = caso.franja() as {
        inicio: string;
        fin: string;
      };
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
        .mockResolvedValueOnce(
          json(
            agendaPayload({
              profesionalId: ID_A,
              franjas: [caso.franja()],
            }),
          ),
        )
        .mockResolvedValueOnce(
          json(
            fichaPayload({
              id: caso.turnoId,
              inicio: franja.inicio,
              fin: franja.fin,
            }),
          ),
        );

      const router = renderAgenda();
      await screen.findByText("Libre").catch(() => undefined);

      fireEvent.click(
        await screen.findByRole("button", {
          name: `Ver detalle del turno de las ${caso.hora}`,
        }),
      );

      const panel = await screen.findByRole("region", {
        name: /detalle del turno/i,
      });
      await within(panel).findByText("Dra. Alpha Ficticia");

      expect(within(panel).getByText(/confirmado|cancelado/i)).toBeDefined();
      expect(within(panel).getByText(/recepcion/i)).toBeDefined();
      expect(within(panel).getByText("Paciente Ficticio")).toBeDefined();
      expect(within(panel).getByText(/12345678/)).toBeDefined();

      expect(router.state.location.pathname).toBe("/staff/agenda");
      expect(router.state.location.search).toBe("");
      expect(router.state.location.hash).toBe("");
    },
  );
});

describe("alta de recepción", () => {
  it("test_alta_valida_crea_el_turno_y_refresca_la_agenda", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD))
      .mockResolvedValueOnce(json(turnoCreado(true), 201))
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            franjas: [
              {
                tipo: "ocupado",
                turno_id: "turno-nuevo-ficticio",
                inicio: `${HOY}T09:00:00-03:00`,
                fin: `${HOY}T09:30:00-03:00`,
                duracion_min: 30,
                estado: "reservado",
                paciente: {
                  id: "paciente-nuevo-ficticio",
                  nombre: "Paciente Nuevo",
                },
              },
            ],
          }),
        ),
      );

    const router = renderAgenda();
    await abrirAlta();
    completarPaciente();
    enviarAlta();

    expect(await screen.findByText("Paciente Nuevo")).toBeDefined();
    expect(screen.queryByRole("form", { name: /alta de turno/i })).toBeNull();

    const [alta] = posteos(fetchMock);
    expect(alta).toBeDefined();
    expect(alta?.body).toMatchObject({
      profesional_id: ID_A,
      inicio: `${HOY}T09:00:00-03:00`,
      duracion_min: 30,
      origen: "recepcion",
      paciente: {
        nombre: "Paciente Nuevo",
        dni: "12345678",
        telefono: "1145550000",
        obra_social: "OS Ficticia",
        email: "paciente.nuevo@ficticio.test",
      },
    });
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2);
    expect(router.state.location.pathname).toBe("/staff/agenda");
    expect(router.state.location.search).toBe("");
  });

  it("test_campos_faltantes_marcan_inputs_y_no_envian", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

    renderAgenda();
    await abrirAlta();
    enviarAlta();

    await waitFor(() =>
      expect(
        screen.getByLabelText("Nombre y apellido").getAttribute("aria-invalid"),
      ).toBe("true"),
    );
    expect(
      screen.getByLabelText("DNI").getAttribute("aria-invalid"),
    ).toBe("true");
    expect(
      screen.getByLabelText("Email").getAttribute("aria-invalid"),
    ).toBe("true");
    expect(posteos(fetchMock)).toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("test_email_invalido_marca_el_campo_y_no_envia", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

    renderAgenda();
    await abrirAlta();
    completarPaciente();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "sin-arroba" },
    });
    enviarAlta();

    await waitFor(() =>
      expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe(
        "true",
      ),
    );
    expect(posteos(fetchMock)).toHaveLength(0);
  });

  it.each([30, 45])(
    "test_opciones_de_duracion_son_multiplos_de_%i_min",
    async (granularidad) => {
      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(
          json({
            items: [profesional(ID_A, "Dra. Alpha Ficticia", granularidad)],
            next_cursor: null,
          }),
        )
        .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

      renderAgenda();
      await abrirAlta();

      const select = screen.getByLabelText("Duración") as HTMLSelectElement;
      const opciones = within(select)
        .getAllByRole("option")
        .map((option) => Number((option as HTMLOptionElement).value));

      expect(opciones).toContain(granularidad);
      expect(opciones.length).toBeGreaterThan(0);
      for (const valor of opciones) {
        expect(valor % granularidad).toBe(0);
      }
    },
  );

  it("test_409_con_alternativos_conserva_los_datos", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD))
      .mockResolvedValueOnce(
        json(
          {
            detail: {
              codigo: "slot_no_disponible",
              alternativos: [
                {
                  inicio: `${HOY}T11:00:00-03:00`,
                  fin: `${HOY}T11:30:00-03:00`,
                  duracion_min: 30,
                },
              ],
            },
          },
          409,
        ),
      );

    renderAgenda();
    await abrirAlta();
    completarPaciente();
    enviarAlta();

    expect(
      await screen.findByText(/el horario elegido ya no está disponible/i),
    ).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe("Paciente Nuevo");

    fireEvent.click(
      await screen.findByRole("button", { name: "11:00 a 11:30" }),
    );
    await waitFor(() =>
      expect(screen.getByText(/horario elegido/i).textContent).toContain(
        "11:00–11:30",
      ),
    );
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe("Paciente Nuevo");
  });

  it("test_409_slot_no_disponible_sin_alternativos_ofrece_reconsultar", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD))
      .mockResolvedValueOnce(
        json({ detail: { codigo: "slot_no_disponible" } }, 409),
      )
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

    renderAgenda();
    await abrirAlta();
    completarPaciente();
    enviarAlta();

    expect(
      await screen.findByText(/el horario elegido ya no está disponible/i),
    ).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe("Paciente Nuevo");

    fireEvent.click(
      screen.getByRole("button", { name: /reconsultar agenda/i }),
    );

    await waitFor(() =>
      expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2),
    );
  });

  it("test_201_sin_mails_informa_sin_marcar_el_turno_como_fallido", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD))
      .mockResolvedValueOnce(json(turnoCreado(false), 201))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

    renderAgenda();
    await abrirAlta();
    completarPaciente();
    enviarAlta();

    expect(
      await screen.findByText(/no se pudieron encolar los mails/i),
    ).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("form", { name: /alta de turno/i })).toBeNull();
    await waitFor(() =>
      expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2),
    );
  });

  it.each(["recepcion", "admin"] as const)(
    "test_%s_ve_la_accion_de_alta",
    async (rol) => {
      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(mePorRol(rol)))
        .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
        .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD));

      renderAgenda();
      await screen.findByText("Libre");

      expect(
        screen.getByRole("button", { name: /crear turno de las 09:00/i }),
      ).toBeDefined();
    },
  );

  it("test_odontologia_no_ve_la_accion_de_alta", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meOdontologo))
      .mockResolvedValueOnce(
        json({
          items: [profesionalA, profesionalB],
          next_cursor: null,
        }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_B,
            franjas: [franjaLibre()],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    expect(
      screen.queryByRole("button", { name: /crear turno/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("form", { name: /alta de turno/i }),
    ).toBeNull();
  });

  it("test_403_defensivo_del_alta_muestra_permiso_generico_sin_exito", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(FRANJA_LIBRE_PAYLOAD))
      .mockResolvedValueOnce(json({ detail: "Sin permiso" }, 403));

    renderAgenda();
    await abrirAlta();
    completarPaciente();
    enviarAlta();

    expect(
      await screen.findByText(/no tenés permiso para esta acción/i),
    ).toBeDefined();
    expect(
      screen.getByRole("form", { name: /alta de turno/i }),
    ).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe("Paciente Nuevo");
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(1);
    expect(screen.queryByText(/turno creado/i)).toBeNull();
  });
});

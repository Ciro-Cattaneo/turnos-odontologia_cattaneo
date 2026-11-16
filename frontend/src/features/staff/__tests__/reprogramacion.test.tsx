/**
 * Reprogramación de turnos staff (§7.1): fecha destino + franjas libres +
 * duración múltiplo, 409 con alternativos, 422 turno_no_editable y estados
 * terminales sin acción.
 * Capa: integración (router en memoria, fetch stubbeado en el borde).
 * # AC frontend-agenda-staff/Reprogramación y cambio de duración.
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
import { hoyEnConsultorio } from "../../../shared/format";

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

function urlsDe(mock: ReturnType<typeof vi.fn>, sufijo: string): string[] {
  return mock.mock.calls
    .map((call) => call[0])
    .filter(
      (url): url is string => typeof url === "string" && url.includes(sufijo),
    );
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

function agendaPayload(franjas: unknown[]): unknown {
  return {
    profesional_id: ID_A,
    vista: "dia",
    dias: [{ fecha: HOY, franjas }],
    next_cursor: "2026-11-14",
    ultima_actualizacion: null,
  };
}

function franjaOcupada(inicio = "10:00", fin = "10:30"): unknown {
  return {
    tipo: "ocupado",
    turno_id: "turno-ficticio-repro",
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
    estado: "confirmado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

function franjaLibre(inicio: string, fin: string): unknown {
  return {
    tipo: "libre",
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
  };
}

function fichaPayload(params: {
  inicio: string;
  fin: string;
  estado?: string;
  duracion?: number;
}): unknown {
  return {
    id: "turno-ficticio-repro",
    estado: params.estado ?? "confirmado",
    origen: "recepcion",
    inicio: params.inicio,
    fin: params.fin,
    duracion_min: params.duracion ?? 30,
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

function reprogramacionOut(params: {
  inicio: string;
  fin: string;
  duracion?: number;
}): unknown {
  return {
    id: "turno-ficticio-repro",
    estado: "confirmado",
    inicio: params.inicio,
    fin: params.fin,
    duracion_min: params.duracion ?? 30,
    notificaciones_encoladas: true,
  };
}

const FICHA_ACTUAL = fichaPayload({
  inicio: `${HOY}T10:00:00-03:00`,
  fin: `${HOY}T10:30:00-03:00`,
});

const AGENDA_ACTUAL = agendaPayload([franjaOcupada()]);
const AGENDA_DESTINO = agendaPayload([
  franjaOcupada(),
  franjaLibre("14:00", "14:30"),
]);

async function abrirDetalle(hora = "10:00"): Promise<HTMLElement> {
  await screen.findByText("Ocupado");
  fireEvent.click(
    screen.getByRole("button", {
      name: `Ver detalle del turno de las ${hora}`,
    }),
  );
  const panel = await screen.findByRole("region", {
    name: /detalle del turno/i,
  });
  await within(panel).findByText("Dra. Alpha Ficticia");
  return panel;
}

async function abrirReprogramacion(panel: HTMLElement): Promise<void> {
  fireEvent.click(
    within(panel).getByRole("button", { name: /reprogramar turno/i }),
  );
  await within(panel).findByRole("form", { name: /reprogramar turno/i });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("reprogramación de turnos", () => {
  it("test_reprogramacion_a_un_slot_libre_actualiza_ficha_y_agenda", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO))
      .mockResolvedValueOnce(
        json(
          reprogramacionOut({
            inicio: `${HOY}T14:00:00-03:00`,
            fin: `${HOY}T14:30:00-03:00`,
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T14:00:00-03:00`,
            fin: `${HOY}T14:30:00-03:00`,
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(agendaPayload([franjaOcupada("14:00", "14:30")])),
      );

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    await within(panel).findByRole("option", { name: "14:00–14:30" });
    fireEvent.change(
      within(panel).getByLabelText(/horario destino/i),
      { target: { value: `${HOY}T14:00:00-03:00` } },
    );
    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    expect(await within(panel).findByText("14:00–14:30")).toBeDefined();
    expect(within(panel).getByText(/turno reprogramado/i)).toBeDefined();

    const [reprogramacion] = mutaciones(fetchMock, "PUT");
    expect(reprogramacion).toBeDefined();
    expect(reprogramacion?.url).toBe("/api/turnos/turno-ficticio-repro");
    expect(reprogramacion?.body).toEqual({
      inicio: `${HOY}T14:00:00-03:00`,
      duracion_min: 30,
    });
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(3);
  });

  it("test_cambio_de_duracion_valido_recalcula_el_fin", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO))
      .mockResolvedValueOnce(
        json(
          reprogramacionOut({
            inicio: `${HOY}T10:00:00-03:00`,
            fin: `${HOY}T11:00:00-03:00`,
            duracion: 60,
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T10:00:00-03:00`,
            fin: `${HOY}T11:00:00-03:00`,
            duracion: 60,
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(agendaPayload([franjaOcupada("10:00", "11:00")])),
      );

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    fireEvent.change(within(panel).getByLabelText(/duración/i), {
      target: { value: "60" },
    });
    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    expect(await within(panel).findByText("10:00–11:00")).toBeDefined();
    expect(within(panel).getByText("60 min")).toBeDefined();

    const [reprogramacion] = mutaciones(fetchMock, "PUT");
    expect(reprogramacion?.body).toEqual({
      inicio: `${HOY}T10:00:00-03:00`,
      duracion_min: 60,
    });
  });

  it("test_409_en_el_destino_muestra_alternativos_sin_mover_el_turno", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO))
      .mockResolvedValueOnce(
        json(
          {
            detail: {
              codigo: "slot_no_disponible",
              alternativos: [
                {
                  inicio: `${HOY}T15:00:00-03:00`,
                  fin: `${HOY}T15:30:00-03:00`,
                  duracion_min: 30,
                },
              ],
            },
          },
          409,
        ),
      );

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    await within(panel).findByRole("option", { name: "14:00–14:30" });
    fireEvent.change(within(panel).getByLabelText(/horario destino/i), {
      target: { value: `${HOY}T14:00:00-03:00` },
    });
    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    expect(
      await within(panel).findByText(/el horario elegido ya no está disponible/i),
    ).toBeDefined();
    expect(
      await within(panel).findByRole("button", { name: "15:00 a 15:30" }),
    ).toBeDefined();
    expect(within(panel).getByText("10:00–10:30")).toBeDefined();
    expect(within(panel).queryByText(/turno reprogramado/i)).toBeNull();
    expect(urlsDe(fetchMock, "/turno-ficticio-repro")).toHaveLength(2);
  });

  it("test_400_por_campo_marca_inicio_y_no_refresca_la_ficha", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO))
      .mockResolvedValueOnce(
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

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    await waitFor(() =>
      expect(
        within(panel)
          .getByLabelText(/horario destino/i)
          .getAttribute("aria-invalid"),
      ).toBe("true"),
    );
    expect(
      within(panel).getByText(/debe ser una fecha futura/i),
    ).toBeDefined();
    expect(within(panel).getByText("10:00–10:30")).toBeDefined();
    expect(within(panel).queryByText(/turno reprogramado/i)).toBeNull();
    expect(urlsDe(fetchMock, "/turno-ficticio-repro")).toHaveLength(2);
  });

  it("test_422_turno_no_editable_informa_y_refresca_sin_exito", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO))
      .mockResolvedValueOnce(
        json({ detail: { codigo: "turno_no_editable" } }, 422),
      )
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T10:00:00-03:00`,
            fin: `${HOY}T10:30:00-03:00`,
            estado: "cancelado",
          }),
        ),
      )
      .mockResolvedValueOnce(json(AGENDA_ACTUAL));

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar reprogramación/i }),
    );

    expect(
      await within(panel).findByText(/ya no se puede editar/i),
    ).toBeDefined();
    expect(within(panel).getByText("cancelado")).toBeDefined();
    expect(within(panel).queryByText(/turno reprogramado/i)).toBeNull();
    expect(
      within(panel).queryByRole("button", { name: /reprogramar turno/i }),
    ).toBeNull();
  });

  it.each(["reservado", "confirmado"] as const)(
    "test_turno_%s_ofrece_reprogramar_y_cancelar",
    async (estado) => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date(AHORA));

      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
        .mockResolvedValueOnce(json(AGENDA_ACTUAL))
        .mockResolvedValueOnce(
          json(
            fichaPayload({
              inicio: `${HOY}T10:00:00-03:00`,
              fin: `${HOY}T10:30:00-03:00`,
              estado,
            }),
          ),
        );

      renderAgenda();
      const panel = await abrirDetalle();

      expect(
        within(panel).getByRole("button", { name: /reprogramar turno/i }),
      ).toBeDefined();
      expect(
        within(panel).getByRole("button", { name: /cancelar turno/i }),
      ).toBeDefined();
    },
  );

  it.each(["cancelado", "atendido", "ausente"] as const)(
    "test_turno_%s_no_ofrece_reprogramacion",
    async (estado) => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date(AHORA));

      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
        .mockResolvedValueOnce(json(AGENDA_ACTUAL))
        .mockResolvedValueOnce(
          json(
            fichaPayload({
              inicio: `${HOY}T10:00:00-03:00`,
              fin: `${HOY}T10:30:00-03:00`,
              estado,
            }),
          ),
        );

      renderAgenda();
      const panel = await abrirDetalle();

      expect(
        within(panel).queryByRole("button", { name: /reprogramar turno/i }),
      ).toBeNull();
    },
  );
});

describe("reprogramación en la zona del consultorio", () => {
  it("test_fecha_inicial_del_formulario_es_el_dia_del_turno", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(AGENDA_ACTUAL))
      .mockResolvedValueOnce(json(FICHA_ACTUAL))
      .mockResolvedValueOnce(json(AGENDA_DESTINO));

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirReprogramacion(panel);

    const fecha = within(panel).getByLabelText(/fecha destino/i);
    expect((fecha as HTMLInputElement).value).toBe(HOY);
    expect(hoyEnConsultorio(new Date(AHORA))).toBe(HOY);
  });
});

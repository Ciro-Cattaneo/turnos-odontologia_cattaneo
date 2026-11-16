/**
 * Cancelación staff normal y forzada <3 h (§7.2–§7.3): motivo obligatorio,
 * `DELETE` con body JSON, 422 motivo_requerido/turno_ya_cancelado/
 * turno_no_cancelable sin reintento y 403 de odontología.
 * Capa: integración (router en memoria, fetch stubbeado en el borde).
 * # AC frontend-agenda-staff/Cancelación normal y forzada con motivo.
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
const ID_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const HOY = "2026-11-13";
const AHORA = "2026-11-13T12:00:00Z";

type Rol = "recepcion" | "odontologo";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const meOdontologo = {
  email: "odontologo@ficticio.test",
  rol: "odontologo",
  profesional_id: ID_B,
};

function mePorRol(rol: Rol): unknown {
  return rol === "odontologo" ? meOdontologo : meRecepcion;
}

const profesionalA = {
  id: ID_A,
  nombre: "Dra. Alpha Ficticia",
  especialidad: "Clínica",
  matricula: null,
  duracion_default_min: 30,
  ultima_actualizacion: null,
};
const profesionalB = {
  id: ID_B,
  nombre: "Dr. Beta Ficticio",
  especialidad: "Ortodoncia",
  matricula: "MP-000",
  duracion_default_min: 45,
  ultima_actualizacion: null,
};

const PROFESIONALES_PAGE = {
  items: [profesionalA, profesionalB],
  next_cursor: null,
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
  contentType: string | null;
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
      const headers = new Headers(init.headers);
      encontradas.push({
        url,
        method,
        body: JSON.parse(crudo) as unknown,
        contentType: headers.get("Content-Type"),
      });
    }
  }
  return encontradas;
}

function agendaPayload(profesionalId: string, franjas: unknown[]): unknown {
  return {
    profesional_id: profesionalId,
    vista: "dia",
    dias: [{ fecha: HOY, franjas }],
    next_cursor: "2026-11-14",
    ultima_actualizacion: null,
  };
}

function franjaOcupada(inicio = "14:00", fin = "14:30"): unknown {
  return {
    tipo: "ocupado",
    turno_id: "turno-ficticio-cancel",
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
    estado: "confirmado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

function franjaLibre(inicio = "14:00", fin = "14:30"): unknown {
  return {
    tipo: "libre",
    inicio: `${HOY}T${inicio}:00-03:00`,
    fin: `${HOY}T${fin}:00-03:00`,
    duracion_min: 30,
  };
}

function franjaCerrada(): unknown {
  return {
    tipo: "cerrado",
    turno_id: "turno-ficticio-cancel",
    inicio: `${HOY}T14:00:00-03:00`,
    fin: `${HOY}T14:30:00-03:00`,
    duracion_min: 30,
    estado: "cancelado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

function fichaPayload(params: {
  inicio: string;
  fin: string;
  estado?: string;
  profesionalId?: string;
}): unknown {
  return {
    id: "turno-ficticio-cancel",
    estado: params.estado ?? "confirmado",
    origen: "recepcion",
    inicio: params.inicio,
    fin: params.fin,
    duracion_min: 30,
    profesional: {
      id: params.profesionalId ?? ID_A,
      nombre:
        params.profesionalId === ID_B
          ? "Dr. Beta Ficticio"
          : "Dra. Alpha Ficticia",
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

function cancelacionOut(): unknown {
  return {
    id: "turno-ficticio-cancel",
    estado: "cancelado",
    inicio: `${HOY}T14:00:00-03:00`,
    fin: `${HOY}T14:30:00-03:00`,
    duracion_min: 30,
    notificaciones_encoladas: true,
    mensaje: "Turno cancelado",
  };
}

const FICHA_MAS_DE_3H = fichaPayload({
  inicio: `${HOY}T14:00:00-03:00`,
  fin: `${HOY}T14:30:00-03:00`,
});
const FICHA_MENOS_DE_3H = fichaPayload({
  inicio: `${HOY}T11:00:00-03:00`,
  fin: `${HOY}T11:30:00-03:00`,
});

async function abrirDetalle(hora = "14:00"): Promise<HTMLElement> {
  await screen.findByText("Ocupado");
  fireEvent.click(
    screen.getByRole("button", {
      name: `Ver detalle del turno de las ${hora}`,
    }),
  );
  const panel = await screen.findByRole("region", {
    name: /detalle del turno/i,
  });
  await within(panel).findByText(/Dra\. Alpha Ficticia|Dr\. Beta Ficticio/);
  return panel;
}

async function abrirCancelacion(panel: HTMLElement): Promise<void> {
  fireEvent.click(
    within(panel).getByRole("button", { name: /cancelar turno/i }),
  );
  await within(panel).findByRole("form", { name: /cancelar turno/i });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("cancelación staff", () => {
  it("test_cancelacion_con_3_horas_o_mas_confirma_sin_motivo_y_libera_el_slot", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaOcupada()])))
      .mockResolvedValueOnce(json(FICHA_MAS_DE_3H))
      .mockResolvedValueOnce(json(cancelacionOut()))
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T14:00:00-03:00`,
            fin: `${HOY}T14:30:00-03:00`,
            estado: "cancelado",
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(agendaPayload(ID_A, [franjaLibre(), franjaCerrada()])),
      );

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirCancelacion(panel);

    expect(within(panel).queryByLabelText(/motivo/i)).toBeNull();
    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(await within(panel).findByText(/turno cancelado/i)).toBeDefined();
    expect(within(panel).getByText("cancelado")).toBeDefined();
    expect(await screen.findByText("Libre")).toBeDefined();

    const [cancelacion] = mutaciones(fetchMock, "DELETE");
    expect(cancelacion).toBeDefined();
    expect(cancelacion?.url).toBe("/api/turnos/turno-ficticio-cancel");
    expect(cancelacion?.body).toEqual({});
    expect(cancelacion?.contentType).toContain("application/json");
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2);
  });

  it("test_menos_de_3_horas_sin_motivo_no_permite_confirmar_ni_envia", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(
        json(agendaPayload(ID_A, [franjaOcupada("11:00", "11:30")])),
      )
      .mockResolvedValueOnce(json(FICHA_MENOS_DE_3H));

    renderAgenda();
    const panel = await abrirDetalle("11:00");
    await abrirCancelacion(panel);

    const motivo = within(panel).getByLabelText(/motivo/i);
    expect(motivo.getAttribute("aria-required")).toBe("true");
    const confirmar = within(panel).getByRole("button", {
      name: /confirmar cancelación/i,
    });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(confirmar);
    await waitFor(() =>
      expect(mutaciones(fetchMock, "DELETE")).toHaveLength(0),
    );
  });

  it("test_menos_de_3_horas_con_motivo_cancela_y_envia_el_motivo", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(
        json(agendaPayload(ID_A, [franjaOcupada("11:00", "11:30")])),
      )
      .mockResolvedValueOnce(json(FICHA_MENOS_DE_3H))
      .mockResolvedValueOnce(json(cancelacionOut()))
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T11:00:00-03:00`,
            fin: `${HOY}T11:30:00-03:00`,
            estado: "cancelado",
          }),
        ),
      )
      .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaLibre()])));

    renderAgenda();
    const panel = await abrirDetalle("11:00");
    await abrirCancelacion(panel);

    fireEvent.change(within(panel).getByLabelText(/motivo/i), {
      target: { value: "Reprogramación del paciente" },
    });
    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(await within(panel).findByText(/turno cancelado/i)).toBeDefined();
    const [cancelacion] = mutaciones(fetchMock, "DELETE");
    expect(cancelacion?.body).toEqual({
      motivo: "Reprogramación del paciente",
    });
  });

  it("test_422_motivo_requerido_reabre_el_campo_y_no_cancela", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaOcupada()])))
      .mockResolvedValueOnce(json(FICHA_MAS_DE_3H))
      .mockResolvedValueOnce(
        json({ detail: { codigo: "motivo_requerido" } }, 422),
      );

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirCancelacion(panel);

    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(
      await within(panel).findByText(/se requiere un motivo/i),
    ).toBeDefined();
    const motivo = within(panel).getByLabelText(/motivo/i);
    expect(motivo.getAttribute("aria-required")).toBe("true");
    expect(
      (
        within(panel).getByRole("button", {
          name: /confirmar cancelación/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(within(panel).queryByText(/turno cancelado\./i)).toBeNull();
    expect(urlsDe(fetchMock, "/turno-ficticio-cancel")).toHaveLength(2);
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(1);
  });

  it.each([
    ["turno_ya_cancelado", "cancelado", /el turno ya está cancelado/i],
    [
      "turno_no_cancelable",
      "atendido",
      /el turno no se puede cancelar en su estado actual/i,
    ],
  ] as const)(
    "test_422_%s_informa_el_estado_sin_reintento",
    async (codigo, estadoFinal, mensaje) => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date(AHORA));

      const fetchMock = stubFetch();
      fetchMock
        .mockResolvedValueOnce(json(meRecepcion))
        .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
        .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaOcupada()])))
        .mockResolvedValueOnce(json(FICHA_MAS_DE_3H))
        .mockResolvedValueOnce(json({ detail: { codigo } }, 422))
        .mockResolvedValueOnce(
          json(
            fichaPayload({
              inicio: `${HOY}T14:00:00-03:00`,
              fin: `${HOY}T14:30:00-03:00`,
              estado: estadoFinal,
            }),
          ),
        )
        .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaCerrada()])));

      renderAgenda();
      const panel = await abrirDetalle();
      await abrirCancelacion(panel);

      fireEvent.click(
        within(panel).getByRole("button", { name: /confirmar cancelación/i }),
      );

      expect(await within(panel).findByText(mensaje)).toBeDefined();
      expect(
        within(panel).queryByRole("button", { name: /cancelar turno/i }),
      ).toBeNull();
      expect(
        within(panel).queryByRole("button", { name: /reintentar/i }),
      ).toBeNull();
      expect(urlsDe(fetchMock, "/turno-ficticio-cancel")).toHaveLength(3);
      expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2);
    },
  );

  it("test_403_defensivo_de_cancelacion_muestra_permiso_generico_sin_exito", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(agendaPayload(ID_A, [franjaOcupada()])))
      .mockResolvedValueOnce(json(FICHA_MAS_DE_3H))
      .mockResolvedValueOnce(json({ detail: "Sin permiso" }, 403));

    renderAgenda();
    const panel = await abrirDetalle();
    await abrirCancelacion(panel);

    fireEvent.click(
      within(panel).getByRole("button", { name: /confirmar cancelación/i }),
    );

    expect(
      await within(panel).findByText(/no tenés permiso para esta acción/i),
    ).toBeDefined();
    expect(
      within(panel).getByRole("form", { name: /cancelar turno/i }),
    ).toBeDefined();
    expect(within(panel).queryByText(/turno cancelado\./i)).toBeNull();
    expect(urlsDe(fetchMock, "/turno-ficticio-cancel")).toHaveLength(2);
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(1);
  });

  it("test_odontologia_no_ve_la_accion_de_cancelar", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(AHORA));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(mePorRol("odontologo")))
      .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
      .mockResolvedValueOnce(json(agendaPayload(ID_B, [franjaOcupada()])))
      .mockResolvedValueOnce(
        json(
          fichaPayload({
            inicio: `${HOY}T14:00:00-03:00`,
            fin: `${HOY}T14:30:00-03:00`,
            profesionalId: ID_B,
          }),
        ),
      );

    renderAgenda();
    const panel = await abrirDetalle();

    expect(
      within(panel).queryByRole("button", { name: /cancelar turno/i }),
    ).toBeNull();
  });
});

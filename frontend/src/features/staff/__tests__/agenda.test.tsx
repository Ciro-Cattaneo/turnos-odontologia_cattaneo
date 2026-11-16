/**
 * Agenda staff día/semana: cache por clave, selector, navegación de fecha y
 * render de franjas (capa: integración, router en memoria, fetch de borde).
 * # AC frontend-agenda-staff/Agenda día/semana por profesional — §5.1–§5.3.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";
import { addDias, hoyEnConsultorio } from "../../../shared/format";

const ID_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const ID_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const HOY = hoyEnConsultorio();

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

function urlAgenda(
  id: string,
  vista: "dia" | "semana",
  fecha: string,
): string {
  return `/api/profesionales/${id}/agenda?vista=${vista}&fecha=${fecha}`;
}

interface DiaPayload {
  fecha: string;
  franjas: unknown[];
}

function agendaPayload(params: {
  profesionalId: string;
  vista?: "dia" | "semana";
  fecha: string;
  dias?: DiaPayload[];
  ultima?: string | null;
}): unknown {
  const vista = params.vista ?? "dia";
  return {
    profesional_id: params.profesionalId,
    vista,
    dias: params.dias ?? [{ fecha: params.fecha, franjas: [] }],
    next_cursor: addDias(params.fecha, vista === "dia" ? 1 : 7),
    ultima_actualizacion: params.ultima ?? null,
  };
}

function franjaLibre(fecha: string = HOY): unknown {
  return {
    tipo: "libre",
    inicio: `${fecha}T09:00:00-03:00`,
    fin: `${fecha}T09:30:00-03:00`,
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

function franjaBloqueada(fecha: string = HOY): unknown {
  return {
    tipo: "bloqueado",
    inicio: `${fecha}T11:00:00-03:00`,
    fin: `${fecha}T12:00:00-03:00`,
    motivo: "Capacitación",
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

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("agenda staff", () => {
  it("test_cambiar_de_profesional_consulta_solo_la_agenda_elegida", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA, profesionalB], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_B,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaOcupada()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, "dia", HOY),
    ]);

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: ID_B },
    });

    expect(await screen.findByText("Paciente Ficticio")).toBeDefined();
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, "dia", HOY),
      urlAgenda(ID_B, "dia", HOY),
    ]);
  });

  it("test_volver_a_una_clave_cacheada_no_reconsulta", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA, profesionalB], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_B,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaOcupada()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: ID_B },
    });
    await screen.findByText("Paciente Ficticio");

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: ID_A },
    });

    expect(await screen.findByText("Libre")).toBeDefined();
    expect(urlsDe(fetchMock, "/agenda?")).toHaveLength(2);
  });

  it("test_boton_actualizar_reconsulta_la_clave_visible", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaOcupada()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    fireEvent.click(screen.getByRole("button", { name: "Actualizar" }));

    expect(await screen.findByText("Paciente Ficticio")).toBeDefined();
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, "dia", HOY),
      urlAgenda(ID_A, "dia", HOY),
    ]);
  });

  it("test_odontologo_solo_puede_elegir_su_propia_agenda", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meOdontologo))
      .mockResolvedValueOnce(
        json({ items: [profesionalA, profesionalB], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_B,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    const selector = screen.getByLabelText("Profesional") as HTMLSelectElement;
    expect(selector.value).toBe(ID_B);
    expect(within(selector).getAllByRole("option")).toHaveLength(1);
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_B, "dia", HOY),
    ]);
  });

  it("test_cambiar_a_vista_semana_consulta_la_semana_y_muestra_siete_dias", async () => {
    const diasSemana = Array.from({ length: 7 }, (_, indice) => ({
      fecha: addDias(HOY, indice),
      franjas: indice === 0 ? [franjaLibre()] : [],
    }));
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            vista: "semana",
            fecha: HOY,
            dias: diasSemana,
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            vista: "semana",
            fecha: addDias(HOY, 7),
            dias: diasSemana.map((dia) => ({
              fecha: addDias(dia.fecha, 7),
              franjas: [],
            })),
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    fireEvent.click(screen.getByRole("button", { name: "Semana" }));

    await waitFor(() =>
      expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(7),
    );
    expect(urlsDe(fetchMock, "/agenda?")).toContain(
      urlAgenda(ID_A, "semana", HOY),
    );

    fireEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));

    await waitFor(() =>
      expect(urlsDe(fetchMock, "/agenda?")).toContain(
        urlAgenda(ID_A, "semana", addDias(HOY, 7)),
      ),
    );
  });

  it("test_navegar_al_dia_siguiente_consulta_la_fecha_del_consultorio", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
          }),
        ),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: addDias(HOY, 1),
            dias: [{ fecha: addDias(HOY, 1), franjas: [franjaOcupada()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    fireEvent.click(screen.getByRole("button", { name: "Día siguiente" }));

    expect(await screen.findByText("Paciente Ficticio")).toBeDefined();
    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, "dia", HOY),
      urlAgenda(ID_A, "dia", addDias(HOY, 1)),
    ]);
  });

  it("test_fecha_inicial_es_el_dia_del_consultorio_no_el_del_navegador", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-13T02:30:00Z"));

    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: "2026-11-12",
            dias: [{ fecha: "2026-11-12", franjas: [franjaLibre()] }],
          }),
        ),
      );

    renderAgenda();
    await screen.findByText("Libre");

    expect(urlsDe(fetchMock, "/agenda?")).toEqual([
      urlAgenda(ID_A, "dia", "2026-11-12"),
    ]);
  });

  it("test_vista_dia_muestra_franjas_libre_ocupado_y_bloqueado", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [
              {
                fecha: HOY,
                franjas: [
                  franjaLibre(),
                  franjaOcupada(),
                  franjaBloqueada(),
                ],
              },
            ],
          }),
        ),
      );

    renderAgenda();

    expect(await screen.findByText("Libre")).toBeDefined();
    expect(screen.getByText("Ocupado")).toBeDefined();
    expect(screen.getByText("Paciente Ficticio")).toBeDefined();
    expect(screen.getByText("Bloqueado")).toBeDefined();
    expect(screen.getByText("Capacitación")).toBeDefined();
  });

  it("test_turnos_cerrados_del_dia_se_listan_como_historial", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaCerrada()] }],
          }),
        ),
      );

    renderAgenda();

    expect(
      await screen.findByRole("heading", { name: /turnos cerrados del día/i }),
    ).toBeDefined();
    expect(screen.getByText(/cancelado/i)).toBeDefined();
    expect(screen.getByText("Paciente Cerrado")).toBeDefined();
  });

  it("test_agenda_vacia_muestra_estado_vacio_explicito", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [] }],
          }),
        ),
      );

    renderAgenda();

    expect(
      await screen.findByText(/no hay horarios ni turnos para este período/i),
    ).toBeDefined();
  });

  it("test_ultima_actualizacion_se_muestra_en_la_zona_del_consultorio", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
            ultima: "2026-11-12T11:15:00Z",
          }),
        ),
      );

    renderAgenda();

    expect(
      await screen.findByText(/última actualización: 12\/11\/2026 08:15/i),
    ).toBeDefined();
  });

  it("test_ultima_actualizacion_null_muestra_sin_datos_cargados", async () => {
    const fetchMock = stubFetch();
    fetchMock
      .mockResolvedValueOnce(json(meRecepcion))
      .mockResolvedValueOnce(
        json({ items: [profesionalA], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        json(
          agendaPayload({
            profesionalId: ID_A,
            fecha: HOY,
            dias: [{ fecha: HOY, franjas: [franjaLibre()] }],
            ultima: null,
          }),
        ),
      );

    renderAgenda();

    expect(
      await screen.findByText(/última actualización: sin datos cargados/i),
    ).toBeDefined();
  });
});

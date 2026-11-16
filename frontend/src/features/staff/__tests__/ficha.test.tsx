/**
 * Ficha de turno §8: historial paginado por cursor, corrección de DNI/
 * teléfono/obra social y transiciones de estado válidas por estado y rol.
 * Capa: integración (router en memoria, fetch stubbeado en el borde).
 * # AC frontend-agenda-staff/Corrección de datos del paciente con historial
 * # AC frontend-agenda-staff/Marcado de asistencia con transiciones válidas
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
const TURNO_ID = "turno-ficticio-ficha";
const HOY = "2026-11-13";

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

function getsDe(mock: ReturnType<typeof vi.fn>, sufijo: string): string[] {
  return mock.mock.calls
    .filter((call) => {
      const url: unknown = call[0];
      const init: RequestInit | undefined = call[1] as RequestInit | undefined;
      return (
        typeof url === "string" &&
        url.includes(sufijo) &&
        (init?.method ?? "GET") === "GET"
      );
    })
    .map((call) => call[0] as string);
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

function franjaOcupada(): unknown {
  return {
    tipo: "ocupado",
    turno_id: TURNO_ID,
    inicio: `${HOY}T14:00:00-03:00`,
    fin: `${HOY}T14:30:00-03:00`,
    duracion_min: 30,
    estado: "confirmado",
    paciente: { id: "paciente-ficticio-1", nombre: "Paciente Ficticio" },
  };
}

interface PacienteOverride {
  nombre?: string | null;
  dni?: string | null;
  telefono?: string | null;
  obra_social?: string | null;
  email?: string | null;
  activo?: boolean;
}

interface FichaParams {
  estado?: string;
  profesionalId?: string;
  paciente?: PacienteOverride;
  auditoria?: { items: unknown[]; next_cursor: string | null };
}

function fichaPayload(params: FichaParams = {}): unknown {
  return {
    id: TURNO_ID,
    estado: params.estado ?? "confirmado",
    origen: "recepcion",
    inicio: `${HOY}T14:00:00-03:00`,
    fin: `${HOY}T14:30:00-03:00`,
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
      ...params.paciente,
    },
    auditoria: params.auditoria ?? { items: [], next_cursor: null },
  };
}

function auditoriaItem(
  id: string,
  accion: string,
  detalle: Record<string, unknown>,
  actor: Record<string, unknown> = {
    tipo: "staff",
    id: "staff-ficticio-1",
    rol: "recepcion",
  },
): unknown {
  return {
    id,
    accion,
    actor,
    created_at: "2026-11-13T12:00:00Z",
    detalle,
  };
}

async function abrirDetalle(): Promise<HTMLElement> {
  await screen.findByText("Ocupado");
  fireEvent.click(
    screen.getByRole("button", {
      name: "Ver detalle del turno de las 14:00",
    }),
  );
  const panel = await screen.findByRole("region", {
    name: /detalle del turno/i,
  });
  await within(panel).findByText(/Dra\. Alpha Ficticia|Dr\. Beta Ficticio/);
  return panel;
}

async function abrirCorreccion(panel: HTMLElement): Promise<HTMLElement> {
  fireEvent.click(
    within(panel).getByRole("button", {
      name: /corregir datos del paciente/i,
    }),
  );
  return within(panel).findByRole("form", {
    name: /corregir datos del paciente/i,
  });
}

function abrirFichaCon(
  fetchMock: ReturnType<typeof vi.fn>,
  rol: Rol,
  ficha: unknown,
): void {
  fetchMock
    .mockResolvedValueOnce(json(mePorRol(rol)))
    .mockResolvedValueOnce(json(PROFESIONALES_PAGE))
    .mockResolvedValueOnce(
      json(
        agendaPayload(rol === "odontologo" ? ID_B : ID_A, [franjaOcupada()]),
      ),
    )
    .mockResolvedValueOnce(json(ficha));
  renderAgenda();
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ficha de turno §8", () => {
  it("test_historial_dos_paginas_deduplica_por_id", async () => {
    const fetchMock = stubFetch();
    const primera = fichaPayload({
      auditoria: {
        items: [
          auditoriaItem("aud-1", "accion-uno", {}),
          auditoriaItem("aud-2", "accion-dos", {}),
        ],
        next_cursor: "cursor-1",
      },
    });
    abrirFichaCon(fetchMock, "recepcion", primera);
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(
      json(
        fichaPayload({
          auditoria: {
            items: [
              auditoriaItem("aud-2", "accion-dos", {}),
              auditoriaItem("aud-3", "accion-tres", {}),
            ],
            next_cursor: null,
          },
        }),
      ),
    );

    fireEvent.click(
      within(panel).getByRole("button", { name: /ver más historial/i }),
    );

    expect(await within(panel).findByText("accion-tres")).toBeDefined();
    expect(within(panel).getAllByText("accion-dos")).toHaveLength(1);
    expect(within(panel).getAllByText("accion-uno")).toHaveLength(1);
    expect(
      within(panel).queryByRole("button", { name: /ver más historial/i }),
    ).toBeNull();
    expect(
      urlsDe(fetchMock, "historial_cursor=cursor-1"),
    ).toHaveLength(1);
  });

  it("test_cursor_invalido_reinicia_el_historial_y_avisa", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(
      fetchMock,
      "recepcion",
      fichaPayload({
        auditoria: {
          items: [
            auditoriaItem("aud-1", "accion-uno", {}),
            auditoriaItem("aud-2", "accion-dos", {}),
          ],
          next_cursor: "cursor-1",
        },
      }),
    );
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: [
            {
              campo: "historial_cursor",
              error: "cursor inválido",
              tipo: "cursor_invalido",
            },
          ],
        },
        400,
      ),
    );
    fetchMock.mockResolvedValueOnce(
      json(
        fichaPayload({
          auditoria: {
            items: [
              auditoriaItem("aud-1", "accion-uno", {}),
              auditoriaItem("aud-2", "accion-dos", {}),
            ],
            next_cursor: null,
          },
        }),
      ),
    );

    fireEvent.click(
      within(panel).getByRole("button", { name: /ver más historial/i }),
    );

    expect(
      await within(panel).findByText(/cursor dejó de ser válido/i),
    ).toBeDefined();
    expect(within(panel).getAllByText("accion-uno")).toHaveLength(1);
    expect(
      within(panel).queryByRole("button", { name: /ver más historial/i }),
    ).toBeNull();
    expect(getsDe(fetchMock, TURNO_ID)).toHaveLength(3);
  });

  it("test_payload_de_cambio_desconocido_se_muestra_como_par_clave_valor", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(
      fetchMock,
      "recepcion",
      fichaPayload({
        auditoria: {
          items: [
            auditoriaItem("aud-1", "accion-rara", {
              cambios: { campo_raro: { antes: "x", despues: "y" } },
            }),
            auditoriaItem("aud-2", "accion-motivo", { motivo: "Reprogramación" }),
            auditoriaItem("aud-3", "accion-simple", {
              cambios: { telefono: "114" },
            }),
          ],
          next_cursor: null,
        },
      }),
    );
    const panel = await abrirDetalle();

    expect(within(panel).getByText(/campo_raro: x → y/)).toBeDefined();
    expect(
      within(panel).getByText(/Motivo: — → Reprogramación/),
    ).toBeDefined();
    expect(within(panel).getByText(/Teléfono: — → 114/)).toBeDefined();
  });

  it("test_correccion_valida_refresca_ficha_e_historial", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload());
    const panel = await abrirDetalle();
    const form = await abrirCorreccion(panel);

    expect(within(form).queryByLabelText(/nombre/i)).toBeNull();
    expect(within(form).queryByLabelText(/email/i)).toBeNull();
    expect(within(form).getAllByText(/no editable/i)).toHaveLength(2);

    fireEvent.change(within(form).getByLabelText("Teléfono"), {
      target: { value: "1145559999" },
    });
    fireEvent.change(within(form).getByLabelText("Obra social"), {
      target: { value: "OS Nueva" },
    });

    fetchMock.mockResolvedValueOnce(
      json({
        id: TURNO_ID,
        paciente: {
          id: "paciente-ficticio-1",
          nombre: "Paciente Ficticio",
          dni: "12345678",
          telefono: "1145559999",
          obra_social: "OS Nueva",
          email: "paciente@ficticio.test",
          activo: true,
        },
        notificaciones_encoladas: false,
      }),
    );
    fetchMock.mockResolvedValueOnce(
      json(
        fichaPayload({
          paciente: { telefono: "1145559999", obra_social: "OS Nueva" },
          auditoria: {
            items: [
              auditoriaItem("aud-1", "editar_paciente", {
                cambios: {
                  telefono: { antes: "1145550000", despues: "1145559999" },
                  obra_social: { antes: "OS Ficticia", despues: "OS Nueva" },
                },
              }),
            ],
            next_cursor: null,
          },
        }),
      ),
    );

    fireEvent.click(
      within(form).getByRole("button", { name: /guardar corrección/i }),
    );

    expect(await within(panel).findByText("Datos del paciente corregidos.")).toBeDefined();
    expect(within(panel).getByText("1145559999")).toBeDefined();
    expect(within(panel).getByText("OS Nueva")).toBeDefined();
    expect(
      within(panel).getByText(/Teléfono: 1145550000 → 1145559999/),
    ).toBeDefined();

    const puts = mutaciones(fetchMock, "PUT");
    expect(puts).toHaveLength(1);
    expect(puts[0]?.url).toContain("/paciente");
    expect(puts[0]?.body).toEqual({
      dni: "12345678",
      telefono: "1145559999",
      obra_social: "OS Nueva",
    });
  });

  it("test_400_por_campo_marca_el_input_y_no_muestra_exito", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload());
    const panel = await abrirDetalle();
    const form = await abrirCorreccion(panel);

    fireEvent.change(within(form).getByLabelText("DNI"), {
      target: { value: "12" },
    });

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

    await waitFor(() => {
      expect(within(form).getByLabelText("DNI").getAttribute("aria-invalid")).toBe(
        "true",
      );
    });
    expect(
      within(form).getByText(/debe tener 7 u 8 dígitos/i),
    ).toBeDefined();
    expect(
      within(panel).queryByText("Datos del paciente corregidos."),
    ).toBeNull();
    expect(getsDe(fetchMock, TURNO_ID)).toHaveLength(1);
  });

  it("test_409_dni_duplicado_informa_sin_fusionar_y_sin_refrescar", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload());
    const panel = await abrirDetalle();
    const form = await abrirCorreccion(panel);

    fireEvent.change(within(form).getByLabelText("DNI"), {
      target: { value: "87654321" },
    });

    fetchMock.mockResolvedValueOnce(
      json({ detail: { codigo: "dni_duplicado" } }, 409),
    );

    fireEvent.click(
      within(form).getByRole("button", { name: /guardar corrección/i }),
    );

    expect(
      await within(form).findByText(/ya está registrado en otro paciente/i),
    ).toBeDefined();
    expect(within(panel).getByRole("form", { name: /corregir datos/i })).toBeDefined();
    expect(getsDe(fetchMock, TURNO_ID)).toHaveLength(1);
  });

  it("test_turno_cancelado_permite_corregir_datos", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "cancelado" }));
    const panel = await abrirDetalle();
    const form = await abrirCorreccion(panel);

    fireEvent.change(within(form).getByLabelText("Teléfono"), {
      target: { value: "1145551111" },
    });

    fetchMock.mockResolvedValueOnce(
      json({
        id: TURNO_ID,
        paciente: {
          id: "paciente-ficticio-1",
          nombre: "Paciente Ficticio",
          dni: "12345678",
          telefono: "1145551111",
          obra_social: "OS Ficticia",
          email: "paciente@ficticio.test",
          activo: true,
        },
        notificaciones_encoladas: false,
      }),
    );
    fetchMock.mockResolvedValueOnce(
      json(fichaPayload({ estado: "cancelado", paciente: { telefono: "1145551111" } })),
    );

    fireEvent.click(
      within(form).getByRole("button", { name: /guardar corrección/i }),
    );

    expect(await within(panel).findByText("Datos del paciente corregidos.")).toBeDefined();
    expect(within(panel).getByText("1145551111")).toBeDefined();
  });

  it("test_odontologia_no_ve_la_edicion_de_paciente", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(
      fetchMock,
      "odontologo",
      fichaPayload({ profesionalId: ID_B }),
    );
    const panel = await abrirDetalle();

    expect(
      within(panel).queryByRole("button", {
        name: /corregir datos del paciente/i,
      }),
    ).toBeNull();
  });

  it("test_turno_reservado_solo_ofrece_confirmar", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "reservado" }));
    const panel = await abrirDetalle();

    expect(
      within(panel).getByRole("button", { name: "Marcar confirmado" }),
    ).toBeDefined();
    expect(
      within(panel).queryByRole("button", { name: "Marcar atendido" }),
    ).toBeNull();
    expect(
      within(panel).queryByRole("button", { name: "Marcar ausente" }),
    ).toBeNull();
  });

  it("test_turno_confirmado_ofrece_atendido_y_ausente_a_recepcion", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "confirmado" }));
    const panel = await abrirDetalle();

    expect(
      within(panel).getByRole("button", { name: "Marcar atendido" }),
    ).toBeDefined();
    expect(
      within(panel).getByRole("button", { name: "Marcar ausente" }),
    ).toBeDefined();
  });

  it("test_odontologia_confirmado_ve_atendido_y_no_ausente", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(
      fetchMock,
      "odontologo",
      fichaPayload({ estado: "confirmado", profesionalId: ID_B }),
    );
    const panel = await abrirDetalle();

    expect(
      within(panel).getByRole("button", { name: "Marcar atendido" }),
    ).toBeDefined();
    expect(
      within(panel).queryByRole("button", { name: "Marcar ausente" }),
    ).toBeNull();
  });

  it.each(["atendido", "ausente", "cancelado"] as const)(
    "test_turno_%s_no_ofrece_acciones_de_estado",
    async (estado) => {
      const fetchMock = stubFetch();
      abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado }));
      const panel = await abrirDetalle();

      expect(
        within(panel).queryByRole("button", { name: /marcar/i }),
      ).toBeNull();
    },
  );

  it("test_transicion_valida_actualiza_estado_y_acciones", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "reservado" }));
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(
      json({
        id: TURNO_ID,
        estado: "confirmado",
        estado_previo: "reservado",
        notificaciones_encoladas: false,
      }),
    );
    fetchMock.mockResolvedValueOnce(
      json(fichaPayload({ estado: "confirmado" })),
    );
    fetchMock.mockResolvedValueOnce(
      json(agendaPayload(ID_A, [franjaOcupada()])),
    );

    fireEvent.click(
      within(panel).getByRole("button", { name: "Marcar confirmado" }),
    );

    expect(
      await within(panel).findByText("Estado actualizado a confirmado."),
    ).toBeDefined();
    expect(
      within(panel).queryByRole("button", { name: "Marcar confirmado" }),
    ).toBeNull();
    expect(
      within(panel).getByRole("button", { name: "Marcar atendido" }),
    ).toBeDefined();

    const patches = mutaciones(fetchMock, "PATCH");
    expect(patches).toHaveLength(1);
    expect(patches[0]?.body).toEqual({ estado: "confirmado" });
  });

  it("test_422_transicion_invalida_informa_y_refresca_el_estado_real", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "confirmado" }));
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(
      json(
        {
          detail: {
            codigo: "transicion_invalida",
            mensaje: "No se puede pasar de reservado a atendido",
          },
        },
        422,
      ),
    );
    fetchMock.mockResolvedValueOnce(
      json(fichaPayload({ estado: "reservado" })),
    );
    fetchMock.mockResolvedValueOnce(
      json(agendaPayload(ID_A, [franjaOcupada()])),
    );

    fireEvent.click(
      within(panel).getByRole("button", { name: "Marcar atendido" }),
    );

    expect(
      await within(panel).findByText(/transición de estado no es válida/i),
    ).toBeDefined();
    expect(
      within(panel).getByRole("button", { name: "Marcar confirmado" }),
    ).toBeDefined();
    expect(
      within(panel).queryByRole("button", { name: "Marcar atendido" }),
    ).toBeNull();
  });

  it("test_403_de_turno_ajeno_muestra_mensaje_generico_sin_datos", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(
      fetchMock,
      "odontologo",
      fichaPayload({ estado: "confirmado", profesionalId: ID_B }),
    );
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(json({ detail: "Sin permiso" }, 403));

    fireEvent.click(
      within(panel).getByRole("button", { name: "Marcar atendido" }),
    );

    const alerta = await within(panel).findByRole("alert");
    expect(alerta.textContent).toMatch(/no tenés permiso/i);
    expect(alerta.textContent).not.toMatch(/Paciente Ficticio/);
    expect(alerta.textContent).not.toMatch(/12345678/);
    expect(getsDe(fetchMock, TURNO_ID)).toHaveLength(1);
  });

  it("test_404_al_refrescar_la_ficha_cierra_el_panel_y_refresca_la_agenda", async () => {
    const fetchMock = stubFetch();
    abrirFichaCon(fetchMock, "recepcion", fichaPayload({ estado: "reservado" }));
    const panel = await abrirDetalle();

    fetchMock.mockResolvedValueOnce(
      json({
        id: TURNO_ID,
        estado: "confirmado",
        estado_previo: "reservado",
        notificaciones_encoladas: false,
      }),
    );
    fetchMock.mockResolvedValueOnce(json({ detail: "No encontrado" }, 404));
    fetchMock.mockResolvedValueOnce(
      json(agendaPayload(ID_A, [franjaOcupada()])),
    );

    fireEvent.click(
      within(panel).getByRole("button", { name: "Marcar confirmado" }),
    );

    expect(
      await screen.findByText("El turno ya no está disponible."),
    ).toBeDefined();
    await waitFor(() => {
      expect(
        screen.queryByRole("region", { name: /detalle del turno/i }),
      ).toBeNull();
    });
    expect(
      screen.queryByRole("button", { name: /marcar/i }),
    ).toBeNull();
  });
});

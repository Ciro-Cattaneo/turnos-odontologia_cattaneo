/**
 * Cliente API tipado de reserva y cancelación (capa: unit/cliente).
 * Datos ficticios `.test` y DNI sintéticos (regla dura 12).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  ApiHttpError,
  isAlternativosDetail,
  isMensajeDetail,
} from "../client";
import {
  cancelarTurno,
  construirRangoDia,
  crearTurno,
  getDisponibilidadDia,
  getProfesionales,
  isCancelacionOut,
  isDisponibilidadResponse,
  isProfesionalesResponse,
  isTurnoOut,
  type CancelacionOut,
  type DisponibilidadResponse,
  type ProfesionalesResponse,
  type TurnoOut,
} from "../reserva";

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const fetchMock = vi.fn<FetchLike>();

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function profesional(id = "11111111-1111-4111-8111-111111111111") {
  return {
    id,
    nombre: "Dra. Ficticia Test",
    especialidad: "Odontología",
    matricula: "MP-0000",
    duracion_default_min: 30,
    ultima_actualizacion: "2026-11-09T10:00:00+00:00",
  };
}

const disponible: DisponibilidadResponse = {
  profesional_id: "11111111-1111-4111-8111-111111111111",
  slots: [
    {
      inicio: "2026-11-10T09:00:00-03:00",
      fin: "2026-11-10T09:30:00-03:00",
      duracion_min: 30,
    },
  ],
  ultima_actualizacion: null,
};

const turno: TurnoOut = {
  id: "22222222-2222-4222-8222-222222222222",
  estado: "reservado",
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
  profesional: { id: "11111111-1111-4111-8111-111111111111", nombre: "Dra. Ficticia Test" },
  paciente: {
    nombre: "Paciente Ficticio Test",
    dni: "30000001",
    email: "paciente@ejemplo.test",
  },
  token_cancelacion: "33333333-3333-4333-8333-333333333333",
  cancel_url:
    "/cancelar?token=33333333-3333-4333-8333-333333333333&id=22222222-2222-4222-8222-222222222222",
  notificaciones_encoladas: true,
};

const cancelacion: CancelacionOut = {
  id: "22222222-2222-4222-8222-222222222222",
  estado: "cancelado",
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
  notificaciones_encoladas: true,
  mensaje: "El turno fue cancelado",
};

async function capturar<T>(promise: Promise<T>): Promise<unknown> {
  return promise.catch((err: unknown) => err);
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("guards de reserva", () => {
  it("test_guards_aceptan_respuestas_del_contrato", () => {
    const profesionales: ProfesionalesResponse = {
      items: [profesional()],
      next_cursor: null,
    };

    expect(isProfesionalesResponse(profesionales)).toBe(true);
    expect(isDisponibilidadResponse(disponible)).toBe(true);
    expect(isTurnoOut(turno)).toBe(true);
    expect(isCancelacionOut(cancelacion)).toBe(true);
  });

  it("test_guards_rechazan_respuesta_incompleta", () => {
    expect(isProfesionalesResponse({ items: [{ nombre: "sin id" }] })).toBe(false);
    expect(
      isDisponibilidadResponse({ profesional_id: "x", slots: [{ inicio: "a" }] }),
    ).toBe(false);
    expect(isTurnoOut({ ...turno, notificaciones_encoladas: "si" })).toBe(false);
    expect(isCancelacionOut({ ...cancelacion, mensaje: 42 })).toBe(false);
  });
});

describe("errores tipados del cliente", () => {
  it("test_error_400_mapea_campos", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: [
            {
              campo: "paciente.email",
              error: "Formato inválido",
              tipo: "string_pattern_mismatch",
            },
          ],
        },
        400,
      ),
    );

    const err = await capturar(crearTurno({
      profesional_id: "11111111-1111-4111-8111-111111111111",
      inicio: "2026-11-10T09:00:00-03:00",
      paciente: {
        nombre: "Paciente Ficticio Test",
        dni: "30000001",
        telefono: "1100000001",
        obra_social: "Obra Test",
        email: "invalido",
      },
    }));

    expect(err).toBeInstanceOf(ApiHttpError);
    const apiErr = err as ApiHttpError;
    expect(apiErr.status).toBe(400);
    expect(Array.isArray(apiErr.detail)).toBe(true);
    if (Array.isArray(apiErr.detail)) {
      expect(apiErr.detail[0]?.campo).toBe("paciente.email");
    }
  });

  it("test_error_409_expone_alternativos", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: {
            codigo: "slot_ocupado",
            alternativos: [
              {
                inicio: "2026-11-10T09:30:00-03:00",
                fin: "2026-11-10T10:00:00-03:00",
                duracion_min: 30,
              },
            ],
          },
        },
        409,
      ),
    );

    const err = await capturar(crearTurno({
      profesional_id: "11111111-1111-4111-8111-111111111111",
      inicio: "2026-11-10T09:00:00-03:00",
      paciente: {
        nombre: "Paciente Ficticio Test",
        dni: "30000001",
        telefono: "1100000001",
        obra_social: "Obra Test",
        email: "paciente@ejemplo.test",
      },
    }));

    expect(err).toBeInstanceOf(ApiHttpError);
    const apiErr = err as ApiHttpError;
    expect(apiErr.status).toBe(409);
    expect(isAlternativosDetail(apiErr.detail)).toBe(true);
    if (isAlternativosDetail(apiErr.detail)) {
      expect(apiErr.detail.codigo).toBe("slot_ocupado");
      expect(apiErr.detail.alternativos).toHaveLength(1);
    }
  });

  it("test_error_422_expone_contacto", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: {
            codigo: "cancelacion_fuera_de_plazo",
            mensaje: "Faltan menos de 3 horas",
            contacto: "consultorio@ejemplo.test",
          },
        },
        422,
      ),
    );

    const err = await capturar(
      cancelarTurno(
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
      ),
    );

    expect(err).toBeInstanceOf(ApiHttpError);
    const apiErr = err as ApiHttpError;
    expect(apiErr.status).toBe(422);
    expect(isMensajeDetail(apiErr.detail)).toBe(true);
    if (isMensajeDetail(apiErr.detail)) {
      expect(apiErr.detail.contacto).toBe("consultorio@ejemplo.test");
    }
  });

  it("test_error_403_y_404_son_genericos", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "No autorizado" }, 403))
      .mockResolvedValueOnce(jsonResponse({ detail: "No encontrado" }, 404));

    const err403 = await capturar(
      cancelarTurno("22222222-2222-4222-8222-222222222222", "token-invalido"),
    );
    const err404 = await capturar(
      cancelarTurno("22222222-2222-4222-8222-222222222222", "token-invalido"),
    );

    for (const err of [err403, err404]) {
      expect(err).toBeInstanceOf(ApiHttpError);
      const apiErr = err as ApiHttpError;
      expect(apiErr.message).toBe(`backend respondió ${apiErr.status}`);
      expect(isAlternativosDetail(apiErr.detail)).toBe(false);
      expect(isMensajeDetail(apiErr.detail)).toBe(false);
    }
    expect((err403 as ApiHttpError).status).toBe(403);
    expect((err404 as ApiHttpError).status).toBe(404);
  });

  it("test_error_429_expone_retry_after", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Demasiadas consultas" }, 429, {
        "Retry-After": "12",
      }),
    );

    const err = await capturar(getProfesionales());

    expect(err).toBeInstanceOf(ApiHttpError);
    const apiErr = err as ApiHttpError;
    expect(apiErr.status).toBe(429);
    expect(apiErr.retryAfter).toBe(12);
  });

  it("test_red_caida_es_error_de_red_tipado", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const err = await capturar(getProfesionales());

    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("NETWORK_ERROR");
  });
});

describe("armado de requests", () => {
  it("test_disponibilidad_construye_rango_dia_utc_menos_3", async () => {
    expect(construirRangoDia("2026-11-10")).toEqual({
      desde: "2026-11-10T00:00:00-03:00",
      hasta: "2026-11-10T23:59:59-03:00",
    });

    fetchMock.mockResolvedValueOnce(jsonResponse(disponible));

    await getDisponibilidadDia(
      "11111111-1111-4111-8111-111111111111",
      "2026-11-10",
    );

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]), "https://app.test");
    expect(url.pathname).toBe("/api/disponibilidad");
    expect(url.searchParams.get("desde")).toBe("2026-11-10T00:00:00-03:00");
    expect(url.searchParams.get("hasta")).toBe("2026-11-10T23:59:59-03:00");

    fetchMock.mockResolvedValueOnce(jsonResponse(turno));
    await crearTurno({
      profesional_id: "11111111-1111-4111-8111-111111111111",
      inicio: disponible.slots[0]?.inicio ?? "",
      duracion_min: disponible.slots[0]?.duracion_min,
      paciente: {
        nombre: "Paciente Ficticio Test",
        dni: "30000001",
        telefono: "1100000001",
        obra_social: "Obra Test",
        email: "paciente@ejemplo.test",
      },
    });

    const init = fetchMock.mock.calls[1]?.[1];
    const body = JSON.parse(String(init?.body)) as { inicio: string };
    expect(body.inicio).toBe("2026-11-10T09:00:00-03:00");
  });

  it("test_disponibilidad_rango_dia_respeta_fecha_elegida", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(disponible));

    await getDisponibilidadDia(
      "11111111-1111-4111-8111-111111111111",
      "2026-12-31",
    );

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]), "https://app.test");
    expect(url.searchParams.get("desde")).toBe("2026-12-31T00:00:00-03:00");
    expect(url.searchParams.get("hasta")).toBe("2026-12-31T23:59:59-03:00");
  });

  it("test_cancelar_turno_usa_id_y_token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(cancelacion));

    const id = "22222222-2222-4222-8222-222222222222";
    const token = "token/con?caracteres";
    await cancelarTurno(id, token);

    const call = fetchMock.mock.calls[0];
    const url = new URL(String(call?.[0]), "https://app.test");
    expect(url.pathname).toBe(`/api/turnos/${id}`);
    expect([...url.searchParams.keys()]).toEqual(["token"]);
    expect(url.searchParams.get("token")).toBe(token);
    expect(call?.[1]?.method).toBe("DELETE");
  });

  it("test_cancelar_turno_token_plano_no_agrega_parametros", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(cancelacion));

    await cancelarTurno(
      "22222222-2222-4222-8222-222222222222",
      "33333333-3333-4333-8333-333333333333",
    );

    const call = fetchMock.mock.calls[0];
    const url = new URL(String(call?.[0]), "https://app.test");
    expect(url.pathname).toBe(
      "/api/turnos/22222222-2222-4222-8222-222222222222",
    );
    expect([...url.searchParams.keys()]).toEqual(["token"]);
    expect(call?.[1]?.body).toBeUndefined();
    expect(call?.[1]?.headers).toBeUndefined();
  });

  it("test_get_profesionales_itera_next_cursor_dos_paginas", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          items: [profesional("11111111-1111-4111-8111-111111111111")],
          next_cursor: "22222222-2222-4222-8222-222222222222",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [profesional("33333333-3333-4333-8333-333333333333")],
          next_cursor: null,
        }),
      );

    const items = await getProfesionales();

    expect(items).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondUrl = new URL(
      String(fetchMock.mock.calls[1]?.[0]),
      "https://app.test",
    );
    expect(secondUrl.searchParams.get("cursor")).toBe(
      "22222222-2222-4222-8222-222222222222",
    );
  });

  it("test_get_profesionales_pagina_unica_no_repite_request", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [profesional("11111111-1111-4111-8111-111111111111")],
        next_cursor: null,
      }),
    );

    const items = await getProfesionales();

    expect(items).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstUrl = new URL(
      String(fetchMock.mock.calls[0]?.[0]),
      "https://app.test",
    );
    expect(firstUrl.searchParams.has("cursor")).toBe(false);
  });
});

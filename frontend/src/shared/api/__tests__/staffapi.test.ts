/**
 * Cliente HTTP staff: endpoints y guards estrictos (capa: unit, fetch de borde).
 * Sin MSW ni user-event: `fetch` se stubbea solo en la frontera.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import type { Slot } from "../client";
import {
  cambiarEstado,
  cancelar,
  corregirPaciente,
  crearTurnoRecepcion,
  getAgenda,
  getFallidas,
  getFicha,
  getProfesionalesStaff,
  isAgendaResponse,
  isCancelacionStaffOut,
  isCorreccionOut,
  isEstadoOut,
  isFallidasPage,
  isFichaOut,
  isLoginOut,
  isLogoutOut,
  isMeOut,
  isReprogramacionOut,
  isTurnoStaffOut,
  login,
  logout,
  me,
  reprogramar,
} from "../staff";

const TURNO_ID = "22222222-2222-4222-8222-222222222222";
const PROF_ID = "11111111-1111-4111-8111-111111111111";
const PAC_ID = "44444444-4444-4444-8444-444444444444";

const loginOut = { email: "recepcion@ficticio.test", rol: "recepcion" };
const meOut = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const logoutOut = { ok: true };
const profesional = {
  id: PROF_ID,
  nombre: "Dra. Ficticia",
  especialidad: null,
  matricula: "MP-0000",
  duracion_default_min: 30,
  ultima_actualizacion: null,
};
const profesionalesPage = { items: [profesional], next_cursor: null };
const slot: Slot = {
  inicio: "2026-10-19T12:00:00+00:00",
  fin: "2026-10-19T12:30:00+00:00",
  duracion_min: 30,
};
const pacienteMin = { id: PAC_ID, nombre: "Paciente Ficticio" };
const agenda = {
  profesional_id: PROF_ID,
  vista: "dia",
  dias: [
    {
      fecha: "2026-10-19",
      franjas: [
        { tipo: "libre", ...slot },
        {
          tipo: "ocupado",
          turno_id: TURNO_ID,
          ...slot,
          estado: "reservado",
          paciente: pacienteMin,
        },
        {
          tipo: "bloqueado",
          inicio: slot.inicio,
          fin: slot.fin,
          motivo: "feriado ficticio",
        },
        {
          tipo: "cerrado",
          turno_id: TURNO_ID,
          ...slot,
          estado: "cancelado",
          paciente: pacienteMin,
        },
      ],
    },
  ],
  next_cursor: "2026-10-20",
  ultima_actualizacion: null,
};
const turnoStaff = {
  id: TURNO_ID,
  estado: "reservado",
  ...slot,
  notificaciones_encoladas: true,
};
const reprogramacion = {
  id: TURNO_ID,
  estado: "reservado",
  ...slot,
  notificaciones_encoladas: true,
};
const estadoOut = {
  id: TURNO_ID,
  estado: "confirmado",
  estado_previo: "reservado",
  notificaciones_encoladas: true,
};
const ficha = {
  id: TURNO_ID,
  estado: "reservado",
  origen: "online",
  inicio: slot.inicio,
  fin: slot.fin,
  duracion_min: 30,
  profesional: { id: PROF_ID, nombre: "Dra. Ficticia", especialidad: null },
  paciente: {
    id: PAC_ID,
    nombre: "Paciente Ficticio",
    dni: "30000001",
    telefono: "+5491100000001",
    obra_social: "OS Ficticia",
    email: "paciente@ficticio.test",
    activo: true,
  },
  auditoria: {
    items: [
      {
        id: "55555555-5555-4555-8555-555555555555",
        accion: "crear",
        actor: { id: "staff-1", rol: "recepcion" },
        created_at: "2026-10-19T12:00:00+00:00",
        detalle: { estado_nuevo: "reservado" },
      },
    ],
    next_cursor: null,
  },
};
const correccion = {
  id: TURNO_ID,
  paciente: {
    id: PAC_ID,
    nombre: "Paciente Ficticio",
    dni: "30000001",
    telefono: "+5491100000002",
    obra_social: "OS Ficticia",
    email: "paciente@ficticio.test",
    activo: true,
  },
  notificaciones_encoladas: true,
};
const cancelacion = {
  id: TURNO_ID,
  estado: "cancelado",
  ...slot,
  notificaciones_encoladas: true,
  mensaje: "Turno cancelado",
};
const fallidas = {
  items: [
    {
      id: "66666666-6666-4666-8666-666666666666",
      turno_id: TURNO_ID,
      tipo: "confirmacion",
      intentos: 3,
      error: "SMTP ficticio caído",
      enviar_en: "2026-10-19T12:05:00+00:00",
      paciente_nombre: "Paciente Ficticio",
      paciente_email: "paciente@ficticio.test",
      inicio: slot.inicio,
      fin: slot.fin,
    },
  ],
  next_cursor: null,
};

function stubFetch(payload: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function initDe(fetchMock: ReturnType<typeof vi.fn>, llamada = 0): RequestInit {
  return (fetchMock.mock.calls[llamada]?.[1] ?? {}) as RequestInit;
}

function urlDe(fetchMock: ReturnType<typeof vi.fn>, llamada = 0): string {
  return String(fetchMock.mock.calls[llamada]?.[0] ?? "");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("staff API: endpoints y credenciales", () => {
  it("test_login_envia_post_con_credenciales_include", async () => {
    const fetchMock = stubFetch(loginOut);
    const resultado = await login({
      email: "recepcion@ficticio.test",
      password: "password-ficticia-1",
    });

    expect(resultado).toEqual(loginOut);
    expect(urlDe(fetchMock)).toContain("/api/auth/login");
    expect(initDe(fetchMock).method).toBe("POST");
    expect(initDe(fetchMock).credentials).toBe("include");
    expect(initDe(fetchMock).body).toBe(
      JSON.stringify({
        email: "recepcion@ficticio.test",
        password: "password-ficticia-1",
      }),
    );
  });

  it("test_me_y_logout_usan_credenciales_include", async () => {
    const meFetch = stubFetch(meOut);
    expect(await me()).toEqual(meOut);
    expect(urlDe(meFetch)).toContain("/api/auth/me");
    expect(initDe(meFetch).credentials).toBe("include");

    vi.unstubAllGlobals();
    const logoutFetch = stubFetch(logoutOut);
    expect(await logout()).toEqual(logoutOut);
    expect(urlDe(logoutFetch)).toContain("/api/auth/logout");
    expect(initDe(logoutFetch).method).toBe("POST");
    expect(initDe(logoutFetch).credentials).toBe("include");
  });

  it("test_get_agenda_arma_query_de_vista_y_fecha", async () => {
    const fetchMock = stubFetch(agenda);
    await getAgenda(PROF_ID, "semana", "2026-10-19");

    expect(urlDe(fetchMock)).toContain(`/api/profesionales/${PROF_ID}/agenda`);
    expect(urlDe(fetchMock)).toContain("vista=semana");
    expect(urlDe(fetchMock)).toContain("fecha=2026-10-19");
    expect(initDe(fetchMock).credentials).toBe("include");
  });

  it("test_get_profesionales_staff_pagina_por_cursor", async () => {
    const fetchMock = stubFetch(profesionalesPage);
    const resultado = await getProfesionalesStaff();

    expect(resultado).toEqual([profesional]);
    expect(urlDe(fetchMock)).toContain("/api/profesionales");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("test_crear_turno_recepcion_envia_origen_y_datos", async () => {
    const fetchMock = stubFetch(turnoStaff);
    await crearTurnoRecepcion({
      profesional_id: PROF_ID,
      inicio: slot.inicio,
      duracion_min: 30,
      origen: "recepcion",
      paciente: {
        nombre: "Paciente Ficticio",
        dni: "30000001",
        telefono: "+5491100000001",
        obra_social: "OS Ficticia",
        email: "paciente@ficticio.test",
      },
    });

    expect(urlDe(fetchMock)).toContain("/api/turnos");
    expect(initDe(fetchMock).method).toBe("POST");
    expect(String(initDe(fetchMock).body)).toContain('"origen":"recepcion"');
  });

  it.each([
    ["sin motivo", undefined, "{}"],
    ["con motivo", "cancelación forzada", '{"motivo":"cancelación forzada"}'],
  ])("test_cancelar_%s_envia_delete_con_body", async (_nombre, motivo, body) => {
    const fetchMock = stubFetch(cancelacion);
    await cancelar(TURNO_ID, motivo);

    expect(urlDe(fetchMock)).toContain(`/api/turnos/${TURNO_ID}`);
    expect(initDe(fetchMock).method).toBe("DELETE");
    expect(initDe(fetchMock).body).toBe(body);
  });

  it("test_reprogramar_corregir_y_cambiar_estado_usan_metodos_correctos", async () => {
    const reprogramarFetch = stubFetch(reprogramacion);
    await reprogramar(TURNO_ID, { inicio: slot.inicio, duracion_min: 30 });
    expect(initDe(reprogramarFetch).method).toBe("PUT");
    expect(urlDe(reprogramarFetch)).toContain(`/api/turnos/${TURNO_ID}`);

    vi.unstubAllGlobals();
    const corregirFetch = stubFetch(correccion);
    await corregirPaciente(TURNO_ID, { telefono: "+5491100000002" });
    expect(initDe(corregirFetch).method).toBe("PUT");
    expect(urlDe(corregirFetch)).toContain(`/api/turnos/${TURNO_ID}/paciente`);

    vi.unstubAllGlobals();
    const estadoFetch = stubFetch(estadoOut);
    await cambiarEstado(TURNO_ID, "confirmado");
    expect(initDe(estadoFetch).method).toBe("PATCH");
    expect(urlDe(estadoFetch)).toContain(`/api/turnos/${TURNO_ID}/estado`);
  });

  it("test_ficha_y_fallidas_arman_query_de_cursor", async () => {
    const fichaFetch = stubFetch(ficha);
    await getFicha(TURNO_ID, "cursor-ficha");
    expect(urlDe(fichaFetch)).toContain(`/api/turnos/${TURNO_ID}`);
    expect(urlDe(fichaFetch)).toContain("historial_cursor=cursor-ficha");

    vi.unstubAllGlobals();
    const fallidasFetch = stubFetch(fallidas);
    await getFallidas("cursor-fallidas");
    expect(urlDe(fallidasFetch)).toContain("/api/notificaciones/fallidas");
    expect(urlDe(fallidasFetch)).toContain("limit=20");
    expect(urlDe(fallidasFetch)).toContain("cursor=cursor-fallidas");
    expect(initDe(fallidasFetch).credentials).toBe("include");
  });
});

describe("staff API: guards estrictos", () => {
  it("test_guards_aceptan_payloads_del_contrato", () => {
    expect(isLoginOut(loginOut)).toBe(true);
    expect(isLogoutOut(logoutOut)).toBe(true);
    expect(isMeOut(meOut)).toBe(true);
    expect(isAgendaResponse(agenda)).toBe(true);
    expect(isTurnoStaffOut(turnoStaff)).toBe(true);
    expect(isReprogramacionOut(reprogramacion)).toBe(true);
    expect(isEstadoOut(estadoOut)).toBe(true);
    expect(isFichaOut(ficha)).toBe(true);
    expect(isCorreccionOut(correccion)).toBe(true);
    expect(isCancelacionStaffOut(cancelacion)).toBe(true);
    expect(isFallidasPage(fallidas)).toBe(true);
  });

  const casosInvalido: Array<[string, (value: unknown) => boolean, unknown]> = [
    ["login sin rol", isLoginOut, { email: "a@b.test" }],
    ["logout sin ok", isLogoutOut, {}],
    ["me con rol ajeno", isMeOut, { ...meOut, rol: "paciente" }],
    [
      "agenda con franja desconocida",
      isAgendaResponse,
      {
        ...agenda,
        dias: [{ fecha: "2026-10-19", franjas: [{ tipo: "otro" }] }],
      },
    ],
    [
      "agenda libre sin duracion",
      isAgendaResponse,
      {
        ...agenda,
        dias: [
          {
            fecha: "2026-10-19",
            franjas: [
              { tipo: "libre", inicio: slot.inicio, fin: slot.fin },
            ],
          },
        ],
      },
    ],
    ["turno staff sin encoladas", isTurnoStaffOut, { ...turnoStaff, notificaciones_encoladas: undefined }],
    ["reprogramación sin fin", isReprogramacionOut, { ...reprogramacion, fin: undefined }],
    ["estado sin previo", isEstadoOut, { ...estadoOut, estado_previo: undefined }],
    [
      "ficha sin auditoría",
      isFichaOut,
      { ...ficha, auditoria: undefined },
    ],
    [
      "corrección sin paciente",
      isCorreccionOut,
      { ...correccion, paciente: undefined },
    ],
    ["cancelación sin mensaje", isCancelacionStaffOut, { ...cancelacion, mensaje: undefined }],
    ["fallidas sin items", isFallidasPage, { next_cursor: null }],
  ];

  it.each(casosInvalido)(
    "test_guard_rechaza_%s",
    (_nombre, guard, payload) => {
      expect(guard(payload)).toBe(false);
    },
  );
});

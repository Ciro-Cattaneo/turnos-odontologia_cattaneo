/**
 * Cliente HTTP admin (capa: unit, fetch de borde). Contratos de C-11:
 * guards estrictos, URLs con query keyset y ausencia de `format` (PB-06).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  actualizarProfesional,
  actualizarUsuarioStaff,
  crearProfesional,
  crearUsuarioStaff,
  darDeBajaProfesional,
  darDeBajaUsuarioStaff,
  getReporteOcupacion,
  isProfesionalesAdminPage,
  isProfesionalAdmin,
  isReporteOcupacion,
  isUsuarioStaff,
  isUsuariosStaffPage,
  listarProfesionalesAdmin,
  listarUsuariosStaff,
} from "../admin";

const PROF_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const PROF_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const USUARIO_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

const profesionalActivo = {
  id: PROF_A,
  nombre: "Dra. Ficticia Uno",
  matricula: "MP-0001",
  especialidad: "Ortodoncia",
  duracion_default_min: 45,
  activo: true,
  ultima_actualizacion: null,
};

const profesionalInactivo = {
  id: PROF_B,
  nombre: "Dr. Ficticio Dos",
  matricula: null,
  especialidad: null,
  duracion_default_min: 30,
  activo: false,
  ultima_actualizacion: "2026-11-01T10:00:00+00:00",
};

const profesionalesAdminPage = {
  items: [profesionalActivo, profesionalInactivo],
  next_cursor: null,
};

const profesionalPublico = {
  id: PROF_A,
  nombre: "Dra. Ficticia Uno",
  matricula: "MP-0001",
  especialidad: "Ortodoncia",
  duracion_default_min: 45,
  ultima_actualizacion: null,
};
const profesionalesPublicosPage = {
  items: [profesionalPublico],
  next_cursor: null,
};

const usuarioActivo = {
  id: USUARIO_ID,
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
  activo: true,
};
const usuarioInactivo = {
  id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  email: "recepcion@cattaneo.test",
  rol: "recepcion",
  profesional_id: null,
  activo: false,
};
const usuariosPage = {
  items: [usuarioActivo, usuarioInactivo],
  next_cursor: "cursor-usuarios-2",
};

const filaReporte = {
  profesional: { id: PROF_A, nombre: "Dra. Ficticia Uno", activo: true },
  turnos: 4,
  atendidos: 3,
  ausentes: 1,
  cancelados: 0,
  pendientes: 0,
  minutos_ocupados: 180,
  minutos_disponibles: 240,
  porcentaje_ocupacion: null,
};
const reporte = {
  desde: "2026-10-18",
  hasta: "2026-11-16",
  zona: "America/Argentina/Buenos_Aires",
  items: [filaReporte],
  totales: {
    turnos: 4,
    atendidos: 3,
    ausentes: 1,
    cancelados: 0,
    pendientes: 0,
    minutos_ocupados: 180,
    minutos_disponibles: 240,
    porcentaje_ocupacion: null,
  },
};

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(payload: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(json(payload));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urlDe(fetchMock: ReturnType<typeof vi.fn>, llamada = 0): string {
  return String(fetchMock.mock.calls[llamada]?.[0] ?? "");
}

function initDe(fetchMock: ReturnType<typeof vi.fn>, llamada = 0): RequestInit {
  return (fetchMock.mock.calls[llamada]?.[1] ?? {}) as RequestInit;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("admin API: guards estrictos", () => {
  it("test_profesionales_admin_page_guard_acepta_items_con_activo", () => {
    expect(isProfesionalAdmin(profesionalActivo)).toBe(true);
    expect(isProfesionalesAdminPage(profesionalesAdminPage)).toBe(true);
  });

  it("test_profesionales_admin_page_guard_rechaza_item_sin_activo", () => {
    expect(
      isProfesionalesAdminPage({
        items: [
          {
            id: PROF_A,
            nombre: "Dra. Ficticia Uno",
            matricula: null,
            especialidad: null,
            duracion_default_min: 30,
            ultima_actualizacion: null,
          },
        ],
        next_cursor: null,
      }),
    ).toBe(false);
  });

  it("test_profesionales_admin_page_guard_rechaza_next_cursor_invalido", () => {
    expect(
      isProfesionalesAdminPage({
        items: [profesionalActivo],
        next_cursor: 7,
      }),
    ).toBe(false);
  });

  it("test_usuarios_staff_page_guard_acepta_activo_e_inactivo", () => {
    expect(isUsuarioStaff(usuarioActivo)).toBe(true);
    expect(isUsuarioStaff(usuarioInactivo)).toBe(true);
    expect(isUsuariosStaffPage(usuariosPage)).toBe(true);
  });

  it("test_usuarios_staff_page_guard_rechaza_item_sin_rol", () => {
    expect(
      isUsuariosStaffPage({
        items: [
          {
            id: USUARIO_ID,
            email: "admin@cattaneo.test",
            profesional_id: null,
            activo: true,
          },
        ],
        next_cursor: null,
      }),
    ).toBe(false);
  });

  it("test_reporte_ocupacion_guard_acepta_porcentaje_null", () => {
    expect(isReporteOcupacion(reporte)).toBe(true);
  });

  it("test_reporte_ocupacion_guard_rechaza_totales_incompletos", () => {
    expect(
      isReporteOcupacion({
        ...reporte,
        totales: {
          turnos: 4,
          atendidos: 3,
          ausentes: 1,
          cancelados: 0,
          pendientes: 0,
          minutos_ocupados: 180,
          porcentaje_ocupacion: null,
        },
      }),
    ).toBe(false);
  });
});

describe("admin API: profesionales", () => {
  it("test_listar_profesionales_admin_envia_incluir_inactivos", async () => {
    const fetchMock = stubFetch(profesionalesAdminPage);
    const resultado = await listarProfesionalesAdmin(true);

    expect(resultado).toEqual([profesionalActivo, profesionalInactivo]);
    expect(urlDe(fetchMock)).toContain("/api/profesionales");
    expect(urlDe(fetchMock)).toContain("incluir_inactivos=true");
    expect(initDe(fetchMock).credentials).toBe("include");
  });

  it("test_listar_profesionales_admin_sin_flag_no_envia_parametro", async () => {
    const fetchMock = stubFetch(profesionalesPublicosPage);
    const resultado = await listarProfesionalesAdmin(false);

    expect(urlDe(fetchMock)).toContain("/api/profesionales");
    expect(urlDe(fetchMock)).not.toContain("incluir_inactivos");
    expect(resultado).toEqual([{ ...profesionalPublico, activo: true }]);
  });

  it("test_mutaciones_profesional_usan_metodos_y_body_del_contrato", async () => {
    const crearFetch = stubFetch(profesionalActivo);
    await crearProfesional({
      nombre: "Dra. Ficticia Uno",
      matricula: "MP-0001",
      especialidad: "Ortodoncia",
      duracion_default_min: 45,
    });
    expect(initDe(crearFetch).method).toBe("POST");
    expect(initDe(crearFetch).body).toBe(
      JSON.stringify({
        nombre: "Dra. Ficticia Uno",
        matricula: "MP-0001",
        especialidad: "Ortodoncia",
        duracion_default_min: 45,
      }),
    );

    vi.unstubAllGlobals();
    const editarFetch = stubFetch(profesionalActivo);
    await actualizarProfesional(PROF_A, { nombre: "Dra. Nueva" });
    expect(initDe(editarFetch).method).toBe("PUT");
    expect(urlDe(editarFetch)).toContain(`/api/profesionales/${PROF_A}`);
    expect(initDe(editarFetch).body).toBe('{"nombre":"Dra. Nueva"}');

    vi.unstubAllGlobals();
    const bajaFetch = stubFetch(profesionalInactivo);
    await darDeBajaProfesional(PROF_A);
    expect(initDe(bajaFetch).method).toBe("DELETE");
    expect(urlDe(bajaFetch)).not.toContain("fisico");
    expect(initDe(bajaFetch).body).toBeUndefined();
  });
});

describe("admin API: usuarios staff", () => {
  it("test_listar_usuarios_staff_envia_limit_y_cursor", async () => {
    const fetchMock = stubFetch(usuariosPage);
    const resultado = await listarUsuariosStaff(20, "cursor-usuarios-2");

    expect(resultado).toEqual(usuariosPage);
    expect(urlDe(fetchMock)).toContain("/api/usuarios-staff");
    expect(urlDe(fetchMock)).toContain("limit=20");
    expect(urlDe(fetchMock)).toContain("cursor=cursor-usuarios-2");
    expect(initDe(fetchMock).credentials).toBe("include");
  });

  it("test_crear_usuario_staff_omite_profesional_id_nulo", async () => {
    const fetchMock = stubFetch(usuarioActivo);
    await crearUsuarioStaff({
      email: "admin@cattaneo.test",
      password: "password-ficticia-1",
      rol: "admin",
      profesional_id: null,
    });

    expect(initDe(fetchMock).method).toBe("POST");
    const body = JSON.parse(String(initDe(fetchMock).body)) as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      email: "admin@cattaneo.test",
      password: "password-ficticia-1",
      rol: "admin",
    });
    expect("profesional_id" in body).toBe(false);
  });

  it("test_actualizar_y_baja_usuario_usan_put_y_delete", async () => {
    const editarFetch = stubFetch(usuarioInactivo);
    await actualizarUsuarioStaff(USUARIO_ID, { activo: true });
    expect(initDe(editarFetch).method).toBe("PUT");
    expect(urlDe(editarFetch)).toContain(`/api/usuarios-staff/${USUARIO_ID}`);
    expect(initDe(editarFetch).body).toBe('{"activo":true}');

    vi.unstubAllGlobals();
    const bajaFetch = stubFetch(usuarioInactivo);
    await darDeBajaUsuarioStaff(USUARIO_ID);
    expect(initDe(bajaFetch).method).toBe("DELETE");
    expect(urlDe(bajaFetch)).toContain(`/api/usuarios-staff/${USUARIO_ID}`);
  });
});

describe("admin API: reporte de ocupación", () => {
  it("test_get_reporte_ocupacion_compone_query_con_profesional_id", async () => {
    const fetchMock = stubFetch(reporte);
    const resultado = await getReporteOcupacion(
      "2026-10-18",
      "2026-11-16",
      PROF_A,
    );

    expect(resultado).toEqual(reporte);
    expect(urlDe(fetchMock)).toContain("/api/reportes/ocupacion");
    expect(urlDe(fetchMock)).toContain("desde=2026-10-18");
    expect(urlDe(fetchMock)).toContain("hasta=2026-11-16");
    expect(urlDe(fetchMock)).toContain(`profesional_id=${PROF_A}`);
    expect(urlDe(fetchMock)).not.toContain("format");
  });

  it("test_get_reporte_ocupacion_sin_filtro_no_envia_profesional_id", async () => {
    const fetchMock = stubFetch(reporte);
    await getReporteOcupacion("2026-10-18", "2026-11-16");

    expect(urlDe(fetchMock)).toContain("/api/reportes/ocupacion");
    expect(urlDe(fetchMock)).not.toContain("profesional_id");
    expect(urlDe(fetchMock)).not.toContain("format");
  });
});

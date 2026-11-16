/**
 * Reporte de ocupación admin (capa: integración, router en memoria).
 * Cubre FA rango por defecto, filtro, totales/zona, validación local sin GET,
 * porcentaje nulo/mayor a cien, vacío y ausencia de exportación (RE R1–R5).
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../../App";
import { addDias, hoyEnConsultorio } from "../../../../shared/format";

const meAdmin = {
  email: "admin@cattaneo.test",
  rol: "admin",
  profesional_id: null,
};

const PROF_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const PROF_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const profesionalA = {
  id: PROF_A,
  nombre: "Dra. Ficticia Uno",
  matricula: "MP-0001",
  especialidad: "Ortodoncia",
  duracion_default_min: 45,
  activo: true,
  ultima_actualizacion: null,
};
const profesionalB = {
  id: PROF_B,
  nombre: "Dr. Ficticio Dos",
  matricula: null,
  especialidad: "Clínica",
  duracion_default_min: 30,
  activo: true,
  ultima_actualizacion: null,
};
const profesionalesPage = {
  items: [profesionalA, profesionalB],
  next_cursor: null,
};

const filaNula = {
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
const filaExcedida = {
  profesional: { id: PROF_B, nombre: "Dr. Ficticio Dos", activo: true },
  turnos: 3,
  atendidos: 2,
  ausentes: 0,
  cancelados: 1,
  pendientes: 0,
  minutos_ocupados: 90,
  minutos_disponibles: 60,
  porcentaje_ocupacion: 150,
};
const totalesCompletos = {
  turnos: 7,
  atendidos: 5,
  ausentes: 1,
  cancelados: 1,
  pendientes: 0,
  minutos_ocupados: 270,
  minutos_disponibles: 300,
  porcentaje_ocupacion: 90,
};
const totalesCero = {
  turnos: 0,
  atendidos: 0,
  ausentes: 0,
  cancelados: 0,
  pendientes: 0,
  minutos_ocupados: 0,
  minutos_disponibles: 0,
  porcentaje_ocupacion: null,
};

function reporteCon(
  items: unknown[],
  totales: unknown = totalesCompletos,
): unknown {
  return {
    desde: "2026-10-18",
    hasta: "2026-11-16",
    zona: "America/Argentina/Buenos_Aires",
    items,
    totales,
  };
}

const reporteCompleto = reporteCon([filaNula, filaExcedida]);

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function urlDe(url: string): URL {
  return new URL(url, "http://test.local");
}

function pathDe(url: string): string {
  return urlDe(url).pathname;
}

type Handler = (
  ruta: string,
  method: string,
  init: RequestInit,
) => Response | undefined;

function stubApi(handler: Handler): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((entrada: unknown, init?: RequestInit) => {
    const ruta = String(entrada);
    const metodo = init?.method ?? "GET";
    const respuesta = handler(ruta, metodo, init ?? {});
    if (respuesta === undefined) {
      throw new Error(`fetch no esperado: ${metodo} ${pathDe(ruta)}`);
    }
    return Promise.resolve(respuesta);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubReporte(
  reporte: Handler,
  profesionales: Response = json(profesionalesPage),
): ReturnType<typeof vi.fn> {
  return stubApi((ruta, method, init) => {
    const path = pathDe(ruta);
    if (path === "/api/auth/me") {
      return json(meAdmin);
    }
    if (path === "/api/profesionales") {
      return profesionales;
    }
    if (path === "/api/reportes/ocupacion") {
      return reporte(ruta, method, init);
    }
    return undefined;
  });
}

function renderReporte(): ReturnType<typeof createMemoryRouter> {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/staff/admin/reportes"],
  });
  render(<RouterProvider router={router} />);
  return router;
}

function urlsReporte(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => pathDe(url) === "/api/reportes/ocupacion");
}

function consultar(): void {
  fireEvent.click(screen.getByRole("button", { name: /^consultar$/i }));
}

const HOY = hoyEnConsultorio();
const DESDE_DEFAULT = addDias(HOY, -29);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("reporte de ocupación: carga y filtros", () => {
  it("test_reporte_carga_inicial_pide_ultimos_30_dias_del_consultorio", async () => {
    const fetchMock = stubReporte(() => json(reporteCompleto));

    renderReporte();

    const tabla = await screen.findByRole("table");
    const urls = urlsReporte(fetchMock);
    expect(urls).toHaveLength(1);
    expect(urlDe(urls[0] ?? "").searchParams.get("desde")).toBe(DESDE_DEFAULT);
    expect(urlDe(urls[0] ?? "").searchParams.get("hasta")).toBe(HOY);
    expect(urlDe(urls[0] ?? "").searchParams.has("profesional_id")).toBe(false);
    expect(within(tabla).getByText("Dr. Ficticio Dos")).toBeDefined();
  });

  it("test_reporte_filtro_por_profesional_acota_la_consulta", async () => {
    let llamadas = 0;
    const fetchMock = stubReporte(() => {
      llamadas += 1;
      return json(
        llamadas === 1 ? reporteCompleto : reporteCon([filaNula]),
      );
    });

    renderReporte();
    await screen.findByRole("table");

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_A },
    });
    consultar();

    await waitFor(() =>
      expect(
        within(screen.getByRole("table")).queryByText("Dr. Ficticio Dos"),
      ).toBeNull(),
    );
    const urls = urlsReporte(fetchMock);
    expect(urls).toHaveLength(2);
    expect(urlDe(urls[1] ?? "").searchParams.get("profesional_id")).toBe(
      PROF_A,
    );
    expect(
      within(screen.getByRole("table")).getByText("Dra. Ficticia Uno"),
    ).toBeDefined();
  });

  it("test_reporte_muestra_totales_y_zona_visible", async () => {
    stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    expect(
      screen.getByText(/Zona: America\/Argentina\/Buenos_Aires/),
    ).toBeDefined();
    const totales = screen.getByRole("region", {
      name: /totales del reporte/i,
    });
    expect(within(totales).getByText(/Turnos: 7/)).toBeDefined();
    expect(within(totales).getByText(/Atendidos: 5/)).toBeDefined();
    expect(within(totales).getByText(/Ausentes: 1/)).toBeDefined();
    expect(within(totales).getByText(/Cancelados: 1/)).toBeDefined();
    expect(within(totales).getByText(/Pendientes: 0/)).toBeDefined();
    expect(within(totales).getByText(/Minutos disponibles: 300/)).toBeDefined();
    expect(within(totales).getByText(/Minutos ocupados: 270/)).toBeDefined();
    expect(within(totales).getByText(/Porcentaje: 90 %/)).toBeDefined();
  });
});

describe("reporte de ocupación: validación del rango", () => {
  it("test_reporte_rango_367_no_emite_get_y_marca_hasta", async () => {
    const fetchMock = stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: addDias(HOY, -366) },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: HOY },
    });
    consultar();

    expect(urlsReporte(fetchMock)).toHaveLength(1);
    const hasta = screen.getByLabelText("Hasta");
    expect(hasta.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText(/rango máximo es de 366 días/i)).toBeDefined();
    await waitFor(() => expect(document.activeElement).toBe(hasta));
  });

  it("test_reporte_rango_invertido_no_emite_get", async () => {
    const fetchMock = stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: HOY },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: addDias(HOY, -1) },
    });
    consultar();

    expect(urlsReporte(fetchMock)).toHaveLength(1);
    const hasta = screen.getByLabelText("Hasta");
    expect(hasta.getAttribute("aria-invalid")).toBe("true");
    expect(
      screen.getByText(/no puede ser anterior a la fecha desde/i),
    ).toBeDefined();
    await waitFor(() => expect(document.activeElement).toBe(hasta));
  });

  it("test_reporte_400_hasta_del_backend_marca_el_campo", async () => {
    let llamadas = 0;
    stubReporte(() => {
      llamadas += 1;
      if (llamadas === 1) {
        return json(reporteCompleto);
      }
      return json(
        {
          detail: [
            {
              campo: "hasta",
              error: "rango máximo 366 días",
              tipo: "value_error",
            },
          ],
        },
        400,
      );
    });

    renderReporte();
    await screen.findByRole("table");

    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: addDias(HOY, -5) },
    });
    consultar();

    const hasta = screen.getByLabelText("Hasta");
    await waitFor(() =>
      expect(hasta.getAttribute("aria-invalid")).toBe("true"),
    );
    expect(screen.getByText(/rango máximo 366 días/i)).toBeDefined();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("reporte de ocupación: bordes de filas", () => {
  it("test_reporte_profesional_inexistente_tabla_vacia_sin_error", async () => {
    let llamadas = 0;
    stubReporte(() => {
      llamadas += 1;
      return json(
        llamadas === 1 ? reporteCompleto : reporteCon([], totalesCero),
      );
    });

    renderReporte();
    await screen.findByRole("table");
    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: PROF_A },
    });
    consultar();

    expect(
      await screen.findByText(
        /no hay turnos para el rango y el profesional elegido/i,
      ),
    ).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
    const totales = screen.getByRole("region", {
      name: /totales del reporte/i,
    });
    expect(within(totales).getByText(/Turnos: 0/)).toBeDefined();
    expect(within(totales).getByText(/Minutos ocupados: 0/)).toBeDefined();
  });

  it("test_reporte_porcentaje_null_se_muestra_como_guion", async () => {
    stubReporte(() => json(reporteCon([filaNula])));

    renderReporte();
    await screen.findByRole("table");

    const tabla = screen.getByRole("table");
    const fila = within(tabla).getByText("Dra. Ficticia Uno").closest("tr");
    if (fila === null) {
      throw new Error("No se encontró la fila del reporte");
    }
    expect(within(fila).getByText("—")).toBeDefined();
    expect(within(fila).getByText("180")).toBeDefined();
    expect(within(fila).getByText("240")).toBeDefined();
  });

  it("test_reporte_porcentaje_mayor_a_cien_no_se_recorta", async () => {
    stubReporte(() => json(reporteCon([filaExcedida])));

    renderReporte();
    await screen.findByRole("table");

    const tabla = screen.getByRole("table");
    const fila = within(tabla).getByText("Dr. Ficticio Dos").closest("tr");
    if (fila === null) {
      throw new Error("No se encontró la fila del reporte");
    }
    expect(within(fila).getByText("150 %")).toBeDefined();
    expect(within(fila).queryByText("100 %")).toBeNull();
  });

  it("test_reporte_fila_sin_turnos_muestra_ceros", async () => {
    const filaCero = {
      profesional: { id: PROF_A, nombre: "Dra. Ficticia Uno", activo: true },
      turnos: 0,
      atendidos: 0,
      ausentes: 0,
      cancelados: 0,
      pendientes: 0,
      minutos_ocupados: 0,
      minutos_disponibles: 0,
      porcentaje_ocupacion: 0,
    };
    stubReporte(() => json(reporteCon([filaCero], totalesCero)));

    renderReporte();
    await screen.findByRole("table");

    const tabla = screen.getByRole("table");
    const fila = within(tabla).getByText("Dra. Ficticia Uno").closest("tr");
    if (fila === null) {
      throw new Error("No se encontró la fila del reporte");
    }
    expect(within(fila).getAllByText("0").length).toBeGreaterThanOrEqual(7);
    expect(within(fila).getByText("0 %")).toBeDefined();
  });
});

describe("reporte de ocupación: sin exportación v1", () => {
  it("test_reporte_no_ofrece_controles_de_exportacion", async () => {
    const fetchMock = stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    expect(
      screen.queryByRole("button", {
        name: /exportar|descargar|csv|excel/i,
      }),
    ).toBeNull();
    expect(
      screen.queryByRole("link", {
        name: /exportar|descargar|csv|excel/i,
      }),
    ).toBeNull();
    expect(document.querySelector("a[download]")).toBeNull();
    for (const url of urlsReporte(fetchMock)) {
      expect(urlDe(url).searchParams.has("format")).toBe(false);
    }
  });

  it("test_reporte_muestra_aviso_de_sin_exportacion", async () => {
    stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    expect(screen.getByText(/en v1 el reporte es solo tabla/i)).toBeDefined();
    expect(screen.getByText(/no hay exportación a csv ni excel/i)).toBeDefined();
  });

  it("test_reporte_no_crea_descarga", async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click");
    stubReporte(() => json(reporteCompleto));

    renderReporte();
    await screen.findByRole("table");

    expect(document.querySelectorAll("a[download]").length).toBe(0);
    expect(clickSpy).not.toHaveBeenCalled();
  });
});

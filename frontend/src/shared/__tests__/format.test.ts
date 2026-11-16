/**
 * Formato compartido en la zona del consultorio (capa: unit).
 * Los instantes UTC caen en otro día calendario de Buenos Aires para probar
 * que la TZ del consultorio se impone a la del host.
 */

import { describe, expect, it } from "vitest";

import {
  addDias,
  formatearFechaHora,
  hoyEnConsultorio,
  ZONA_CONSULTORIO,
} from "../format";

describe("formato compartido en zona del consultorio", () => {
  it("test_zona_consultorio_es_buenos_aires", () => {
    expect(ZONA_CONSULTORIO).toBe("America/Argentina/Buenos_Aires");
  });

  it("test_medianoche_utc_usa_dia_calendario_del_consultorio", () => {
    // 2026-11-11T02:30Z = 2026-11-10 23:30 en Buenos Aires.
    expect(hoyEnConsultorio(new Date("2026-11-11T02:30:00Z"))).toBe("2026-11-10");
  });

  it("test_limite_medianoche_consultorio_cambia_el_dia", () => {
    // 2026-11-11T03:00Z = 2026-11-11 00:00 en Buenos Aires.
    expect(hoyEnConsultorio(new Date("2026-11-11T03:00:00Z"))).toBe("2026-11-11");
  });

  it("test_formatear_fecha_hora_usa_hora_del_consultorio", () => {
    expect(formatearFechaHora("2026-11-11T02:30:00Z")).toBe(
      "10/11/2026 23:30",
    );
  });

  it("test_add_dias_cruza_fin_de_mes_y_anio", () => {
    expect(addDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDias("2026-03-01", -1)).toBe("2026-02-28");
  });
});

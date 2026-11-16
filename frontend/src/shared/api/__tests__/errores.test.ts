/**
 * Traducción uniforme de errores staff (capa: unit, D-13).
 * Se construyen errores reales del borde HTTP; no se mockean internos.
 */

import { describe, expect, it } from "vitest";

import {
  ApiError,
  ApiHttpError,
  type FieldError,
  type Slot,
} from "../client";
import { mensajeDeError } from "../errores";

const slot: Slot = {
  inicio: "2026-10-19T12:00:00+00:00",
  fin: "2026-10-19T12:30:00+00:00",
  duracion_min: 30,
};

describe("mensajeDeError staff", () => {
  it("test_400_mapea_campos_y_quita_prefijo_paciente", () => {
    const detail: FieldError[] = [
      { campo: "paciente.dni", error: "DNI inválido", tipo: "value_error" },
      { campo: "inicio", error: "inicio sin zona", tipo: "value_error" },
    ];
    const info = mensajeDeError(new ApiHttpError(400, detail));

    expect(info.kind).toBe("field");
    expect(info.fieldErrors).toEqual({
      dni: "DNI inválido",
      inicio: "inicio sin zona",
    });
  });

  it("test_401_indica_sesion_expirada", () => {
    const info = mensajeDeError(new ApiHttpError(401, "No autenticado"));
    expect(info.kind).toBe("unauthorized");
    expect(info.message).toMatch(/sesi[oó]n/i);
  });

  it("test_403_es_generico_y_no_revela_el_recurso", () => {
    const info = mensajeDeError(new ApiHttpError(403, "Sin permiso"));
    expect(info.kind).toBe("forbidden");
    expect(info.message).toBe("No tenés permiso para esta acción.");
  });

  it("test_404_informa_no_encontrado", () => {
    const info = mensajeDeError(new ApiHttpError(404, "No encontrado"));
    expect(info.kind).toBe("not_found");
    expect(info.message).toMatch(/no encontrado/i);
  });

  it("test_409_slot_no_disponible_expone_alternativos", () => {
    const detail = { codigo: "slot_no_disponible", alternativos: [slot] };
    const info = mensajeDeError(new ApiHttpError(409, detail));

    expect(info.kind).toBe("conflict");
    expect(info.codigo).toBe("slot_no_disponible");
    expect(info.alternativos).toEqual([slot]);
    expect(info.message).toMatch(/horario/i);
  });

  it("test_409_dni_duplicado_informa_sin_fusionar", () => {
    const info = mensajeDeError(new ApiHttpError(409, { codigo: "dni_duplicado" }));
    expect(info.kind).toBe("conflict");
    expect(info.codigo).toBe("dni_duplicado");
    expect(info.message).toMatch(/dni/i);
  });

  it.each([
    ["motivo_requerido", /motivo/i],
    ["turno_no_editable", /editar/i],
    ["turno_ya_cancelado", /cancelado/i],
    ["turno_no_cancelable", /cancelar/i],
    ["transicion_invalida", /transici[oó]n/i],
  ])("test_422_%s_tiene_mensaje_accionable", (codigo, patron) => {
    const detail = { codigo, mensaje: "detalle interno que no se muestra" };
    const info = mensajeDeError(new ApiHttpError(422, detail));

    expect(info.kind).toBe("validation");
    expect(info.codigo).toBe(codigo);
    expect(info.message).toMatch(patron);
    expect(info.message).not.toContain("detalle interno");
  });

  it("test_429_incluye_la_espera_indicada", () => {
    const info = mensajeDeError(new ApiHttpError(429, "Demasiados intentos", 7));
    expect(info.kind).toBe("rate_limit");
    expect(info.message).toContain("7 segundos");
    expect(info.retryAfter).toBe(7);
  });

  it("test_429_sin_retry_after_muestra_espera_generica", () => {
    const info = mensajeDeError(new ApiHttpError(429, "Demasiados intentos"));

    expect(info.kind).toBe("rate_limit");
    expect(info.message).toMatch(/esperá un momento/i);
    expect(info.message).not.toMatch(/\d+ segundos/);
    expect(info.retryAfter).toBeUndefined();
  });

  it("test_error_de_red_invita_a_reintentar", () => {
    const info = mensajeDeError(new ApiError("NETWORK_ERROR", "Failed to fetch"));
    expect(info.kind).toBe("network");
    expect(info.message).toMatch(/conectar/i);
  });

  it("test_mensaje_de_error_409_email_duplicado_especifico", () => {
    const info = mensajeDeError(
      new ApiHttpError(409, { codigo: "email_duplicado" }),
    );

    expect(info.kind).toBe("conflict");
    expect(info.codigo).toBe("email_duplicado");
    expect(info.message).toMatch(/email/i);
    expect(info.message).toMatch(/reactiv/i);
  });

  it("test_mensaje_de_error_422_ultimo_admin_accionable", () => {
    const info = mensajeDeError(
      new ApiHttpError(422, { codigo: "ultimo_admin" }),
    );

    expect(info.kind).toBe("validation");
    expect(info.codigo).toBe("ultimo_admin");
    expect(info.message).toMatch(/al menos un admin activo/i);
  });

  it("test_mensaje_de_error_422_profesional_id_mapea_campo", () => {
    const detail: FieldError[] = [
      {
        campo: "profesional_id",
        error: "El profesional elegido no está activo.",
        tipo: "value_error",
      },
    ];
    const info = mensajeDeError(new ApiHttpError(422, detail));

    expect(info.kind).toBe("field");
    expect(info.fieldErrors).toEqual({
      profesional_id: "El profesional elegido no está activo.",
    });
  });

  it("test_payload_inesperado_es_error_generico", () => {
    const info = mensajeDeError(
      new ApiError("BAD_PAYLOAD", "forma de respuesta inesperada", 200),
      "la agenda",
    );
    expect(info.kind).toBe("unexpected");
    expect(info.message).toMatch(/v[aá]lida/i);
  });
});

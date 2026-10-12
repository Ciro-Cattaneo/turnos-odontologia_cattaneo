/**
 * Shell SPA mínimo (capa: component, Vitest + router en memoria).
 * # AC frontend-shell/S1 — landing render.
 * # AC frontend-shell/S2 — not-found en ruta desconocida.
 * # AC frontend-shell/S3 — sin overflow horizontal a 360px.
 * # AC frontend-shell/S4 — error tipado con backend caído.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { App } from "../../App";
import { ApiError, getHealth } from "../../shared/api/client";

const stylesheet = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../styles.css"),
  "utf8",
);

function renderAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("frontend shell", () => {
  it("test_landing_renderiza_en_ruta_raiz", () => {
    // # AC frontend-shell/S1
    renderAt("/");

    expect(
      screen.getByRole("heading", { name: /turnos odontología/i }),
    ).toBeDefined();
    expect(screen.getByRole("link", { name: /reservar/i })).toBeDefined();
  });

  it("test_ruta_desconocida_muestra_not_found", () => {
    // # AC frontend-shell/S2
    renderAt("/no-existe-xyz");

    expect(screen.getByText(/página no encontrada/i)).toBeDefined();
    expect(screen.getByRole("link", { name: /volver al inicio/i })).toBeDefined();
  });

  it("test_layout_360_sin_overflow_horizontal", () => {
    // # AC frontend-shell/S3 — jsdom no calcula layout real: se verifica el
    // contrato fluido de la hoja (sin anchos fijos > 360) + scrollWidth jsdom.
    window.innerWidth = 360;
    window.dispatchEvent(new Event("resize"));
    renderAt("/");

    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(360);
    expect(stylesheet).toMatch(/box-sizing:\s*border-box/);
    expect(stylesheet).toMatch(/max-width:\s*100%/);
    const fixedWidths = [...stylesheet.matchAll(/(?<!-)width:\s*(\d+)px/g)].map(
      (m) => Number(m[1]),
    );
    expect(fixedWidths.every((w) => w <= 360)).toBe(true);
  });

  it("test_backend_caido_devuelve_error_tipado", async () => {
    // # AC frontend-shell/S4 — red caída (frontera HTTP: mock justificado)
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const caught: unknown = await getHealth().catch((err: unknown) => err);

    expect(caught).toBeInstanceOf(ApiError);
    const apiError = caught as ApiError;
    expect(apiError.code).toBe("NETWORK_ERROR");
    expect(typeof apiError.message).toBe("string");
    vi.unstubAllGlobals();
  });

  it("test_error_http_devuelve_error_tipado_con_status", async () => {
    // # AC frontend-shell/S4 — triangulación: 500 también es ApiError tipado
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("{}", { status: 500, statusText: "Server Error" }),
      ),
    );

    const caught: unknown = await getHealth().catch((err: unknown) => err);

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(500);
    vi.unstubAllGlobals();
  });
});

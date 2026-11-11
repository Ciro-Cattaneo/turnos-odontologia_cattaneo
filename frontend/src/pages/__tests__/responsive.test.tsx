/**
 * Mobile-first 360px y targets táctiles (capa: responsive, R10 S1-S3).
 * jsdom no calcula layout real: el contrato fluido se verifica escaneando
 * todos los `*.module.css` (sin anchos fijos > 360 y `min-height` < 44px).
 */

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { Cancelar } from "../Cancelar";
import { Reservar } from "../Reservar";

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const fetchMock = vi.fn<FetchLike>();

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "../..");

interface ModuloCss {
  ruta: string;
  css: string;
}

function leerModuleCss(dir: string): string[] {
  const rutas: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const ruta = join(dir, entry.name);
    if (entry.isDirectory()) {
      rutas.push(...leerModuleCss(ruta));
    } else if (entry.name.endsWith(".module.css")) {
      rutas.push(ruta);
    }
  }
  return rutas;
}

const modulos: ModuloCss[] = leerModuleCss(SRC_DIR).map((ruta) => ({
  ruta: relative(SRC_DIR, ruta),
  css: readFileSync(ruta, "utf8"),
}));

function anchosFijosInvalidos(): string[] {
  const invalidos: string[] = [];
  for (const { ruta, css } of modulos) {
    for (const match of css.matchAll(/(?<!-)width:\s*(\d+)px/g)) {
      if (Number(match[1]) > 360) {
        invalidos.push(`${ruta}: ${match[0]}`);
      }
    }
  }
  return invalidos;
}

function minHeightsInvalidos(): string[] {
  const invalidos: string[] = [];
  for (const { ruta, css } of modulos) {
    for (const match of css.matchAll(/min-height:\s*(\d+)px/g)) {
      if (Number(match[1]) < 44) {
        invalidos.push(`${ruta}: ${match[0]}`);
      }
    }
  }
  return invalidos;
}

function renderEn360(ui: ReactElement, path: string): void {
  window.innerWidth = 360;
  window.dispatchEvent(new Event("resize"));
  render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const TOKEN = "33333333-3333-4333-8333-333333333333";
const TURNO_ID = "22222222-2222-4222-8222-222222222222";

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("responsive 360px y targets táctiles", () => {
  it("test_reservar_360_sin_overflow", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], next_cursor: null }),
    );

    renderEn360(<Reservar />, "/reservar");

    expect(
      await screen.findByRole("heading", { name: /reservar turno/i }),
    ).toBeDefined();
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(360);
    expect(modulos.length).toBeGreaterThan(0);
    expect(anchosFijosInvalidos()).toEqual([]);
  });

  it("test_cancelar_360_sin_overflow", () => {
    renderEn360(
      <Cancelar />,
      `/cancelar?token=${TOKEN}&id=${TURNO_ID}`,
    );

    expect(screen.getByRole("heading", { name: /cancelar turno/i })).toBeDefined();
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(360);
    expect(anchosFijosInvalidos()).toEqual([]);
  });

  it("test_acciones_tactiles_minimo_44", () => {
    // Cobertura manual: el solapamiento real de acciones se revisa en navegador
    // a 360px; acá se valida el contrato `min-height >= 44px` de los módulos.
    expect(modulos.length).toBeGreaterThan(0);
    const declaraciones = modulos.flatMap(({ css }) => [
      ...css.matchAll(/min-height:\s*\d+px/g),
    ]);
    expect(declaraciones.length).toBeGreaterThan(0);
    expect(minHeightsInvalidos()).toEqual([]);
  });
});

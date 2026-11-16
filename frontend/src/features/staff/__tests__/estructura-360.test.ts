/**
 * §10.2 — Mobile-first 360px sin overflow en login, agenda, ficha y fallidas.
 * jsdom devuelve `scrollWidth === 0` siempre, así que un test de scrollWidth
 * sería tautológico. En su lugar se verifica la estructura CSS que evita el
 * overflow (raíz al 100%, `box-sizing: border-box`, sin anchos fijos) y el
 * orden de tabulación (sin `tabIndex` positivo). La revisión manual de foco y
 * orden de tabulación queda documentada en `tasks.md`.
 */

import { describe, expect, it } from "vitest";

import {
  fuentesDe,
  reglasDeModuleCssStaff,
  reglasDeStylesGlobal,
  type ArchivoFuente,
  type Regla,
} from "./cssStaff";

interface Pantalla {
  archivo: string;
  raiz: string;
}

const PANTALLAS: Pantalla[] = [
  { archivo: "pages/LoginPage.module.css", raiz: "pagina" },
  { archivo: "components/Agenda.module.css", raiz: "pagina" },
  { archivo: "components/TurnoDetalle.module.css", raiz: "panel" },
  { archivo: "pages/NotificacionesPage.module.css", raiz: "pagina" },
];

const PROPIEDADES_DE_ANCHO: ReadonlySet<string> = new Set([
  "width",
  "min-width",
  "max-width",
]);

function normalizarSelector(selector: string): string {
  return selector.replace(/\s+/g, " ").trim();
}

function reglaRaiz(reglas: Regla[], pantalla: Pantalla): Regla | undefined {
  const esperado = `.${pantalla.raiz}`;
  return reglas.find(
    (regla) =>
      regla.archivo === pantalla.archivo &&
      normalizarSelector(regla.selector) === esperado,
  );
}

function valorDe(regla: Regla, propiedad: string): string | undefined {
  return regla.declaraciones.find(
    (declaracion) => declaracion.propiedad === propiedad,
  )?.valor;
}

function fuentesDeProduccion(extension: string): ArchivoFuente[] {
  return fuentesDe(extension).filter(
    (fuente) =>
      !fuente.archivo.startsWith("__tests__/") &&
      !/\.(test|spec)\./.test(fuente.archivo),
  );
}

describe("mobile-first 360px §10.2", () => {
  it.each(PANTALLAS)(
    "test_raiz_de_$archivo_ocupa_el_ancho_disponible_sin_exceder_360px",
    (pantalla) => {
      const raiz = reglaRaiz(reglasDeModuleCssStaff(), pantalla);
      expect(raiz).toBeDefined();
      if (raiz === undefined) {
        return;
      }
      expect(valorDe(raiz, "width")).toBe("100%");
      expect(valorDe(raiz, "max-width")).toBe("100%");
    },
  );

  it("test_styles_globales_aplican_box_sizing_y_evitan_overflow_horizontal", () => {
    const reglas = reglasDeStylesGlobal();
    const reset = reglas.find((regla) =>
      normalizarSelector(regla.selector).includes("::before"),
    );
    const cuerpo = reglas.find((regla) => {
      const selector = normalizarSelector(regla.selector);
      return selector === "html, body";
    });

    expect(reset).toBeDefined();
    expect(cuerpo).toBeDefined();
    if (reset === undefined || cuerpo === undefined) {
      return;
    }
    expect(valorDe(reset, "box-sizing")).toBe("border-box");
    expect(valorDe(cuerpo, "overflow-x")).toBe("clip");
    expect(valorDe(cuerpo, "max-width")).toBe("100%");
  });

  it("test_ningun_module_css_staff_fija_anchos_px_mayores_a_360", () => {
    const infracciones: string[] = [];
    for (const regla of reglasDeModuleCssStaff()) {
      for (const declaracion of regla.declaraciones) {
        if (!PROPIEDADES_DE_ANCHO.has(declaracion.propiedad)) {
          continue;
        }
        const coincidencia = /^(-?\d+(?:\.\d+)?)px$/.exec(
          declaracion.valor.trim(),
        );
        if (coincidencia !== null && Number(coincidencia[1]) > 360) {
          infracciones.push(
            `${regla.archivo} :: ${regla.selector} { ${declaracion.propiedad}: ${declaracion.valor} }`,
          );
        }
      }
    }
    expect(infracciones).toEqual([]);
  });

  it("test_foco_visible_definido_y_sin_tabindex_positivo", () => {
    const foco = reglasDeStylesGlobal().find((regla) =>
      normalizarSelector(regla.selector).includes(":focus-visible"),
    );
    expect(foco).toBeDefined();
    if (foco !== undefined) {
      expect(valorDe(foco, "outline")).toBeDefined();
    }

    const tabIndexPositivo = /tabIndex\s*=\s*\{?\s*["']?[1-9]\d*/;
    const infracciones = [...fuentesDeProduccion(".tsx")]
      .filter((fuente) => tabIndexPositivo.test(fuente.contenido))
      .map((fuente) => fuente.archivo);
    expect(infracciones).toEqual([]);
  });
});

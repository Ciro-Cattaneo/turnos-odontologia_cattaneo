/**
 * §10.1 — Guardas de estilos staff: todo vive en `*.module.css`, sin anchos
 * fijos mayores a 360px ni acciones sin área táctil de 44px, y sin `any`.
 * Vitest/jsdom no aplica CSS modules, así que se inspecciona la fuente.
 */

import { posix } from "node:path";

import { describe, expect, it } from "vitest";

import {
  archivosDe,
  claseBase,
  fuentesDe,
  RAIZ_STAFF,
  reglasDeModuleCssStaff,
  type ArchivoFuente,
  type Regla,
} from "./cssStaff";

function fuentesDeProduccion(extension: string): ArchivoFuente[] {
  return fuentesDe(extension).filter(
    (fuente) =>
      !fuente.archivo.startsWith("__tests__/") &&
      !/\.(test|spec)\./.test(fuente.archivo),
  );
}

const PROPIEDADES_DE_ANCHO: ReadonlySet<string> = new Set([
  "width",
  "min-width",
  "max-width",
]);

const ALTURAS_TACTILES: ReadonlySet<string> = new Set([
  "var(--touch-target)",
  "44px",
]);

function declaracionPx(valor: string): number | null {
  const coincidencia = /^(-?\d+(?:\.\d+)?)px$/.exec(valor.trim());
  return coincidencia === null ? null : Number(coincidencia[1]);
}

function reglasConAnchoFijoMayorA360(): string[] {
  const infracciones: string[] = [];
  for (const regla of reglasDeModuleCssStaff()) {
    for (const declaracion of regla.declaraciones) {
      if (!PROPIEDADES_DE_ANCHO.has(declaracion.propiedad)) {
        continue;
      }
      const px = declaracionPx(declaracion.valor);
      if (px !== null && px > 360) {
        infracciones.push(
          `${regla.archivo} :: ${regla.selector} { ${declaracion.propiedad}: ${declaracion.valor} }`,
        );
      }
    }
  }
  return infracciones;
}

function tieneTouchTarget(regla: Regla): boolean {
  return regla.declaraciones.some(
    (declaracion) =>
      declaracion.propiedad === "min-height" &&
      ALTURAS_TACTILES.has(declaracion.valor.replace(/\s+/g, "")),
  );
}

interface AccionDeclarada {
  archivo: string;
  clase: string;
  cumple: boolean;
}

function clasesDeAccionPorModulo(): Map<string, Set<string>> {
  const porModulo = new Map<string, Set<string>>();
  for (const fuente of fuentesDeProduccion(".tsx")) {
    const importacion = /import\s+styles\s+from\s+["']([^"']+\.module\.css)["']/.exec(
      fuente.contenido,
    );
    if (importacion === null) {
      continue;
    }
    const modulo = posix.normalize(
      posix.join(posix.dirname(fuente.archivo), importacion[1] ?? ""),
    );
    for (const uso of fuente.contenido.matchAll(/styles\.([A-Za-z0-9_]+)/g)) {
      const indice = uso.index ?? 0;
      const antes = fuente.contenido.slice(Math.max(0, indice - 160), indice);
      if (!/<(button|a|Link)\b/.test(antes)) {
        continue;
      }
      const clase = uso[1];
      if (clase === undefined) {
        continue;
      }
      const clases = porModulo.get(modulo) ?? new Set<string>();
      clases.add(clase);
      porModulo.set(modulo, clases);
    }
  }
  return porModulo;
}

function accionesSinTouchTarget(): string[] {
  const reglas = reglasDeModuleCssStaff();
  const acciones = new Map<string, AccionDeclarada>();
  for (const [modulo, clases] of clasesDeAccionPorModulo()) {
    const reglasDelModulo = reglas.filter((regla) => regla.archivo === modulo);
    for (const clase of clases) {
      const clave = `${modulo}::${clase}`;
      acciones.set(clave, {
        archivo: modulo,
        clase,
        cumple: reglasDelModulo.some(
          (regla) =>
            claseBase(regla.selector).includes(clase) && tieneTouchTarget(regla),
        ),
      });
    }
  }
  return [...acciones.values()]
    .filter((accion) => !accion.cumple)
    .map((accion) => `${accion.archivo} :: .${accion.clase}`);
}

describe("estilos staff §10.1", () => {
  it("test_ningun_module_css_staff_declara_anchos_fijos_mayores_a_360px", () => {
    expect(reglasConAnchoFijoMayorA360()).toEqual([]);
  });

  it("test_cada_accion_staff_declara_altura_tactil_de_44px", () => {
    const detectadas = [...clasesDeAccionPorModulo().values()].flatMap(
      (clases) => [...clases],
    );
    expect(detectadas).toContain("accion");
    expect(detectadas).toContain("enlace");
    expect(detectadas).toContain("enviar");
    expect(accionesSinTouchTarget()).toEqual([]);
  });

  it("test_estilos_staff_viven_en_module_css_sin_estilos_inline", () => {
    const hojas = archivosDe(RAIZ_STAFF, ".css");
    const hojasFueraDeModulo = hojas
      .map((ruta) => ruta.replace(/\\/g, "/"))
      .filter((ruta) => !ruta.endsWith(".module.css"));

    const importsInvalidos: string[] = [];
    const estilosInline: string[] = [];
    for (const fuente of [
      ...fuentesDeProduccion(".tsx"),
      ...fuentesDeProduccion(".ts"),
    ]) {
      const implantados = fuente.contenido.matchAll(
        /from\s+["']([^"']+\.css)["']/g,
      );
      for (const importacion of implantados) {
        const ruta = importacion[1];
        if (ruta !== undefined && !ruta.endsWith(".module.css")) {
          importsInvalidos.push(`${fuente.archivo} importa ${ruta}`);
        }
      }
      if (/\bstyle\s*=\s*\{/.test(fuente.contenido)) {
        estilosInline.push(fuente.archivo);
      }
    }

    expect(hojasFueraDeModulo).toEqual([]);
    expect(importsInvalidos).toEqual([]);
    expect(estilosInline).toEqual([]);
  });

  it("test_codigo_staff_no_usa_any", () => {
    const infracciones: string[] = [];
    for (const fuente of [
      ...fuentesDeProduccion(".tsx"),
      ...fuentesDeProduccion(".ts"),
    ]) {
      if (/(:\s*any\b|\bas\s+any\b|<any>|\bany\[\])/.test(fuente.contenido)) {
        infracciones.push(fuente.archivo);
      }
    }
    expect(infracciones).toEqual([]);
  });
});

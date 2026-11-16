/**
 * §6.1, §6.2 y §6.4 — estructura CSS de las pantallas admin: layout fluido a
 * 360px, tabla del reporte con scroll propio y degradación a tarjetas, y
 * acciones con área táctil mínima. Vitest/jsdom no aplica CSS modules ni media
 * queries, así que se inspecciona la fuente reutilizando el lector de C-10.
 */

import { posix } from "node:path";

import { describe, expect, it } from "vitest";

import {
  claseBase,
  fuentesDe,
  reglasDeModuleCssStaff,
  type ArchivoFuente,
  type Regla,
} from "../../__tests__/cssStaff";

const RAIZ_ADMIN = "admin/";

const PROPIEDADES_DE_ANCHO: ReadonlySet<string> = new Set([
  "width",
  "min-width",
  "max-width",
]);

const ALTURAS_TACTILES: ReadonlySet<string> = new Set([
  "var(--touch-target)",
  "44px",
]);

interface ModuloRaiz {
  archivo: string;
  raiz: string;
}

const MODULOS: ModuloRaiz[] = [
  {
    archivo: "admin/pages/AdminProfesionalesPage.module.css",
    raiz: "pagina",
  },
  { archivo: "admin/pages/AdminUsuariosPage.module.css", raiz: "pagina" },
  { archivo: "admin/pages/AdminReportesPage.module.css", raiz: "pagina" },
  { archivo: "admin/components/ProfesionalForm.module.css", raiz: "formulario" },
  { archivo: "admin/components/UsuarioForm.module.css", raiz: "formulario" },
  { archivo: "admin/components/Reporte.module.css", raiz: "filtros" },
  { archivo: "admin/components/SinPermisoAdmin.module.css", raiz: "alerta" },
];

function fuentesAdmin(extension: string): ArchivoFuente[] {
  return fuentesDe(extension).filter(
    (fuente) =>
      fuente.archivo.startsWith(RAIZ_ADMIN) &&
      !fuente.archivo.includes("/__tests__/") &&
      !/\.(test|spec)\./.test(fuente.archivo),
  );
}

function reglasAdmin(): Regla[] {
  return reglasDeModuleCssStaff().filter((regla) =>
    regla.archivo.startsWith(RAIZ_ADMIN),
  );
}

function normalizarSelector(selector: string): string {
  return selector.replace(/\s+/g, " ").trim();
}

function valorDe(regla: Regla | undefined, propiedad: string): string | undefined {
  return regla?.declaraciones.find(
    (declaracion) => declaracion.propiedad === propiedad,
  )?.valor;
}

function declaracionPx(valor: string): number | null {
  const coincidencia = /^(-?\d+(?:\.\d+)?)px$/.exec(valor.trim());
  return coincidencia === null ? null : Number(coincidencia[1]);
}

function tieneTouchTarget(regla: Regla): boolean {
  return regla.declaraciones.some(
    (declaracion) =>
      declaracion.propiedad === "min-height" &&
      ALTURAS_TACTILES.has(declaracion.valor.replace(/\s+/g, "")),
  );
}

function clasesDeAccionPorModulo(): Map<string, Set<string>> {
  const porModulo = new Map<string, Set<string>>();
  for (const fuente of fuentesAdmin(".tsx")) {
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
      const antes = fuente.contenido.slice(
        Math.max(0, (uso.index ?? 0) - 160),
        uso.index ?? 0,
      );
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
  const reglas = reglasAdmin();
  const infracciones: string[] = [];
  for (const [modulo, clases] of clasesDeAccionPorModulo()) {
    const reglasDelModulo = reglas.filter((regla) => regla.archivo === modulo);
    for (const clase of clases) {
      const cumple = reglasDelModulo.some(
        (regla) =>
          claseBase(regla.selector).includes(clase) && tieneTouchTarget(regla),
      );
      if (!cumple) {
        infracciones.push(`${modulo} :: .${clase}`);
      }
    }
  }
  return infracciones;
}

function cssDe(archivo: string): string {
  return fuentesAdmin(".css").find((fuente) => fuente.archivo === archivo)
    ?.contenido ?? "";
}

function bloqueMedia(css: string, consulta: string): string {
  const inicio = css.indexOf(consulta);
  if (inicio === -1) {
    return "";
  }
  const abre = css.indexOf("{", inicio);
  if (abre === -1) {
    return "";
  }
  let profundidad = 0;
  for (let indice = abre; indice < css.length; indice += 1) {
    if (css[indice] === "{") {
      profundidad += 1;
    } else if (css[indice] === "}") {
      profundidad -= 1;
      if (profundidad === 0) {
        return css.slice(abre + 1, indice);
      }
    }
  }
  return "";
}

describe("estilos admin §6", () => {
  it("test_modulos_admin_declaran_layout_fluido", () => {
    const infracciones: string[] = [];
    for (const modulo of MODULOS) {
      const raiz = reglasAdmin().find(
        (regla) =>
          regla.archivo === modulo.archivo &&
          normalizarSelector(regla.selector) === `.${modulo.raiz}`,
      );
      if (raiz === undefined) {
        infracciones.push(`${modulo.archivo} sin raíz .${modulo.raiz}`);
        continue;
      }
      if (valorDe(raiz, "width") !== "100%") {
        infracciones.push(`${modulo.archivo} :: .${modulo.raiz} sin width 100%`);
      }
      if (valorDe(raiz, "max-width") !== "100%") {
        infracciones.push(
          `${modulo.archivo} :: .${modulo.raiz} sin max-width 100%`,
        );
      }
    }

    for (const regla of reglasAdmin()) {
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

    expect(infracciones).toEqual([]);
  });

  it("test_reporte_tabla_no_fuerza_overflow_de_pagina", () => {
    const scroll = reglasAdmin().find(
      (regla) =>
        regla.archivo === "admin/components/Reporte.module.css" &&
        normalizarSelector(regla.selector) === ".tablaScroll",
    );
    expect(scroll).toBeDefined();
    expect(valorDe(scroll, "overflow-x")).toBe("auto");

    const tabla = fuentesAdmin(".tsx").find(
      (fuente) => fuente.archivo === "admin/components/ReporteTabla.tsx",
    );
    expect(tabla).toBeDefined();
    const contenido = tabla?.contenido ?? "";
    expect(contenido).toContain("styles.tablaScroll");
    expect(contenido).toContain("<table");

    const media = bloqueMedia(
      cssDe("admin/components/Reporte.module.css"),
      "@media (max-width: 640px)",
    );
    expect(media).not.toBe("");
    expect(media).toMatch(/\.tabla\s+thead\s*\{[^}]*display:\s*none/);
    expect(media).toMatch(/\.tabla\s*,[\s\S]*?display:\s*block/);

    const raizReporte = reglasAdmin().find(
      (regla) =>
        regla.archivo === "admin/pages/AdminReportesPage.module.css" &&
        normalizarSelector(regla.selector) === ".pagina",
    );
    expect(valorDe(raizReporte, "width")).toBe("100%");
    expect(valorDe(raizReporte, "max-width")).toBe("100%");
  });

  it("test_acciones_admin_declaran_alto_minimo_44", () => {
    const detectadas = [...clasesDeAccionPorModulo().values()].flatMap(
      (clases) => [...clases],
    );
    expect(detectadas).toContain("accion");
    expect(detectadas).toContain("secundario");
    expect(detectadas).toContain("enviar");
    expect(detectadas).toContain("consultar");
    expect(detectadas).toContain("cargarMas");
    expect(accionesSinTouchTarget()).toEqual([]);
  });
});

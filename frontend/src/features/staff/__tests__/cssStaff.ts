/**
 * Lector mínimo de `*.module.css` y fuentes staff para los tests de estilos,
 * mobile-first 360px y a11y estructural (§10.1, §10.2). jsdom no aplica CSS
 * modules ni calcula `scrollWidth`, así que la verificación se hace sobre la
 * fuente CSS y la estructura de los componentes.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const RAIZ_FRONTEND = process.cwd();

export const RAIZ_STAFF = resolve(
  RAIZ_FRONTEND,
  "src",
  "features",
  "staff",
);
export const RUTA_STYLES_GLOBAL = resolve(RAIZ_FRONTEND, "src", "styles.css");

export interface Declaracion {
  propiedad: string;
  valor: string;
}

export interface Regla {
  archivo: string;
  selector: string;
  declaraciones: Declaracion[];
}

export interface ArchivoFuente {
  archivo: string;
  contenido: string;
}

function etiqueta(ruta: string): string {
  return relative(RAIZ_STAFF, ruta).replace(/\\/g, "/");
}

export function archivosDe(raiz: string, extension: string): string[] {
  const encontrados: string[] = [];
  for (const entrada of readdirSync(raiz, { withFileTypes: true })) {
    const ruta = join(raiz, entrada.name);
    if (entrada.isDirectory()) {
      encontrados.push(...archivosDe(ruta, extension));
    } else if (entrada.isFile() && entrada.name.endsWith(extension)) {
      encontrados.push(ruta);
    }
  }
  return encontrados;
}

export function fuentesDe(extension: string): ArchivoFuente[] {
  return archivosDe(RAIZ_STAFF, extension).map((ruta) => ({
    archivo: etiqueta(ruta),
    contenido: readFileSync(ruta, "utf8"),
  }));
}

function declaracionesDe(cuerpo: string): Declaracion[] {
  const declaraciones: Declaracion[] = [];
  for (const trozo of cuerpo.split(";")) {
    const separador = trozo.indexOf(":");
    if (separador === -1) {
      continue;
    }
    const propiedad = trozo.slice(0, separador).trim().toLowerCase();
    const valor = trozo.slice(separador + 1).trim();
    if (propiedad === "" || valor === "") {
      continue;
    }
    declaraciones.push({ propiedad, valor });
  }
  return declaraciones;
}

export function leerReglas(ruta: string, archivo: string): Regla[] {
  const css = readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const reglas: Regla[] = [];
  const patron = /([^{}]+)\{([^{}]*)\}/g;
  let coincidencia = patron.exec(css);
  while (coincidencia !== null) {
    const selector = (coincidencia[1] ?? "").trim();
    const cuerpo = coincidencia[2] ?? "";
    if (selector !== "" && !selector.startsWith("@")) {
      reglas.push({
        archivo,
        selector,
        declaraciones: declaracionesDe(cuerpo),
      });
    }
    coincidencia = patron.exec(css);
  }
  return reglas;
}

export function reglasDeModuleCssStaff(): Regla[] {
  return archivosDe(RAIZ_STAFF, ".module.css").flatMap((ruta) =>
    leerReglas(ruta, etiqueta(ruta)),
  );
}

export function reglasDeStylesGlobal(): Regla[] {
  return leerReglas(RUTA_STYLES_GLOBAL, "styles.css");
}

export function claseBase(selector: string): string[] {
  const clases: string[] = [];
  for (const parte of selector.split(",")) {
    const limpio = parte.trim();
    if (limpio === "" || limpio.includes(":") || limpio.includes("[")) {
      continue;
    }
    const coincidencias = limpio.matchAll(/\.([A-Za-z0-9_-]+)/g);
    for (const coincidencia of coincidencias) {
      const clase = coincidencia[1];
      if (clase !== undefined) {
        clases.push(clase);
      }
    }
  }
  return clases;
}

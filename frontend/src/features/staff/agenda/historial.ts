/**
 * Lectura defensiva del `detalle` de auditoría (D-11): el backend no garantiza
 * un shape fijo por acción, así que se mapean los campos conocidos y el resto
 * se muestra como pares clave/valor.
 */

const ETIQUETAS: Record<string, string> = {
  dni: "DNI",
  telefono: "Teléfono",
  obra_social: "Obra social",
  nombre: "Nombre",
  email: "Email",
  estado: "Estado",
  inicio: "Inicio",
  fin: "Fin",
  duracion_min: "Duración",
  motivo: "Motivo",
};

const CLAVES_META: readonly string[] = [
  "actor",
  "origen",
  "notificaciones_encoladas",
  "cambios",
  "estado_previo",
  "estado_nuevo",
];

export interface CambioHistorial {
  campo: string;
  etiqueta: string;
  antes: string;
  despues: string;
}

function esRegistro(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function texto(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value === "" ? "—" : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "—";
  }
}

function etiqueta(campo: string): string {
  return ETIQUETAS[campo] ?? campo;
}

function cambiosDesde(value: unknown): CambioHistorial[] {
  if (!esRegistro(value)) {
    return [];
  }
  return Object.entries(value).map(([campo, cambio]) => {
    if (esRegistro(cambio) && ("antes" in cambio || "despues" in cambio)) {
      return {
        campo,
        etiqueta: etiqueta(campo),
        antes: texto(cambio["antes"]),
        despues: texto(cambio["despues"]),
      };
    }
    return {
      campo,
      etiqueta: etiqueta(campo),
      antes: "—",
      despues: texto(cambio),
    };
  });
}

export function cambiosDeDetalle(
  detalle: Record<string, unknown>,
): CambioHistorial[] {
  const cambios = cambiosDesde(detalle["cambios"]);
  if (cambios.length > 0) {
    return cambios;
  }
  const previo = detalle["estado_previo"];
  const nuevo = detalle["estado_nuevo"];
  if (typeof previo === "string" && typeof nuevo === "string") {
    return [
      { campo: "estado", etiqueta: "Estado", antes: previo, despues: nuevo },
    ];
  }
  return Object.entries(detalle)
    .filter(([campo]) => !CLAVES_META.includes(campo))
    .map(([campo, valor]) => ({
      campo,
      etiqueta: etiqueta(campo),
      antes: "—",
      despues: texto(valor),
    }));
}

export function actorDeDetalle(actor: Record<string, unknown>): string {
  const rol = actor["rol"];
  if (typeof rol === "string" && rol !== "") {
    return rol;
  }
  const tipo = actor["tipo"];
  return typeof tipo === "string" && tipo !== "" ? tipo : "staff";
}

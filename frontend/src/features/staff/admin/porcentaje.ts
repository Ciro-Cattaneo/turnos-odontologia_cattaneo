/** Porcentaje de ocupación visible (D-5): `null` → "—", sin recorte a 100. */

export function formatearPorcentaje(valor: number | null): string {
  if (valor === null) {
    return "—";
  }
  return `${valor} %`;
}

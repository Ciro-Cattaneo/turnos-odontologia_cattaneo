/** Grilla de duración de profesional: 5–240 en pasos de 5 (AP R1). */

export const OPCIONES_DURACION_PROFESIONAL: readonly number[] = Array.from(
  { length: 48 },
  (_valor, indice) => (indice + 1) * 5,
);

export function esDuracionProfesionalValida(valor: number): boolean {
  return (
    Number.isInteger(valor) &&
    valor >= 5 &&
    valor <= 240 &&
    valor % 5 === 0
  );
}

/**
 * Configuración compartida de la UI. `CANCEL_HOURS_MIN` es espejo del env del
 * backend (D-8): la UI exige motivo antes de enviar y el `422` sigue siendo la
 * red de seguridad cuando los relojes o la config difieren.
 */

export const CANCEL_HOURS_MIN = 3;

const MS_POR_HORA = 60 * 60 * 1000;

/** `true` si falta menos de `CANCEL_HOURS_MIN` para el inicio del turno. */
export function esCancelacionForzada(
  inicio: string,
  ahora: Date = new Date(),
): boolean {
  const inicioMs = new Date(inicio).getTime();
  if (!Number.isFinite(inicioMs)) {
    return false;
  }
  return inicioMs - ahora.getTime() < CANCEL_HOURS_MIN * MS_POR_HORA;
}

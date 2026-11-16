/** Frontera HTTP compartida: respuestas y errores estrictamente tipados (sin `any`). */

export type ApiErrorCode = "NETWORK_ERROR" | "HTTP_ERROR" | "BAD_PAYLOAD";

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number;

  constructor(code: ApiErrorCode, message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export interface FieldError {
  campo: string;
  error: string;
  tipo: string;
}

export interface Slot {
  inicio: string;
  fin: string;
  duracion_min: number;
}

export interface AlternativosDetail {
  codigo: string;
  alternativos: Slot[];
}

export interface MensajeDetail {
  codigo: string;
  mensaje: string;
  contacto?: string;
}

export interface CodigoDetail {
  codigo: string;
}

/** Unión discriminada por la forma del `detail` de cada error del backend. */
export type ApiErrorDetail =
  | FieldError[]
  | AlternativosDetail
  | MensajeDetail
  | CodigoDetail
  | string
  | null;

export class ApiHttpError extends ApiError {
  readonly detail: ApiErrorDetail;
  readonly retryAfter?: number;

  constructor(
    status: number,
    detail: ApiErrorDetail,
    retryAfter?: number,
    message = `backend respondió ${status}`,
  ) {
    super("HTTP_ERROR", message, status);
    this.name = "ApiHttpError";
    this.detail = detail;
    if (retryAfter !== undefined) {
      this.retryAfter = retryAfter;
    }
  }
}

export interface HealthResponse {
  status: string;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isFieldError(value: unknown): value is FieldError {
  return (
    isRecord(value) &&
    typeof value["campo"] === "string" &&
    typeof value["error"] === "string" &&
    typeof value["tipo"] === "string"
  );
}

export function isSlot(value: unknown): value is Slot {
  return (
    isRecord(value) &&
    typeof value["inicio"] === "string" &&
    typeof value["fin"] === "string" &&
    typeof value["duracion_min"] === "number" &&
    Number.isFinite(value["duracion_min"])
  );
}

export function isAlternativosDetail(
  value: ApiErrorDetail,
): value is AlternativosDetail {
  return (
    value !== null &&
    !Array.isArray(value) &&
    typeof value === "object" &&
    "alternativos" in value &&
    Array.isArray(value["alternativos"])
  );
}

export function isMensajeDetail(value: ApiErrorDetail): value is MensajeDetail {
  return (
    value !== null &&
    !Array.isArray(value) &&
    typeof value === "object" &&
    "mensaje" in value &&
    typeof value["mensaje"] === "string"
  );
}

function parseSlotArray(value: unknown): Slot[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const slots: Slot[] = [];
  for (const item of value) {
    if (!isSlot(item)) {
      return null;
    }
    slots.push(item);
  }
  return slots;
}

function parseFieldArray(value: unknown): FieldError[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const fields: FieldError[] = [];
  for (const item of value) {
    if (!isFieldError(item)) {
      return null;
    }
    fields.push(item);
  }
  return fields;
}

function parseDetail(value: unknown): ApiErrorDetail {
  if (typeof value === "string") {
    return value;
  }
  const fields = parseFieldArray(value);
  if (fields !== null) {
    return fields;
  }
  if (isRecord(value)) {
    const codigo = value["codigo"];
    if (typeof codigo === "string") {
      const alternativos = parseSlotArray(value["alternativos"]);
      if (alternativos !== null) {
        return { codigo, alternativos };
      }
      const mensaje = value["mensaje"];
      if (typeof mensaje === "string") {
        const contacto = value["contacto"];
        if (typeof contacto === "string") {
          return { codigo, mensaje, contacto };
        }
        return { codigo, mensaje };
      }
      return { codigo };
    }
  }
  return null;
}

async function readErrorDetail(response: Response): Promise<ApiErrorDetail> {
  try {
    const payload: unknown = await response.json();
    if (isRecord(payload) && "detail" in payload) {
      return parseDetail(payload["detail"]);
    }
    return null;
  } catch {
    return null;
  }
}

function readRetryAfter(response: Response): number | undefined {
  const raw = response.headers.get("Retry-After");
  if (raw === null) {
    return undefined;
  }
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

export async function request<T>(
  url: string,
  isT: (value: unknown) => value is T,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err: unknown) {
    throw new ApiError(
      "NETWORK_ERROR",
      err instanceof Error ? err.message : "backend inalcanzable",
    );
  }
  if (!response.ok) {
    throw new ApiError(
      "HTTP_ERROR",
      `backend respondió ${response.status}`,
      response.status,
    );
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("BAD_PAYLOAD", "respuesta no-JSON del backend", response.status);
  }
  if (!isT(payload)) {
    throw new ApiError("BAD_PAYLOAD", "forma de respuesta inesperada", response.status);
  }
  return payload;
}

/**
 * Igual que `request<T>` pero, ante `!response.ok`, lanza `ApiHttpError` con el
 * `detail` del contrato y `retryAfter` en `429`. No reemplaza a `request<T>`.
 */
export async function requestWithDetail<T>(
  url: string,
  isT: (value: unknown) => value is T,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err: unknown) {
    throw new ApiError(
      "NETWORK_ERROR",
      err instanceof Error ? err.message : "backend inalcanzable",
    );
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    const retryAfter =
      response.status === 429 ? readRetryAfter(response) : undefined;
    throw new ApiHttpError(response.status, detail, retryAfter);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("BAD_PAYLOAD", "respuesta no-JSON del backend", response.status);
  }
  if (!isT(payload)) {
    throw new ApiError("BAD_PAYLOAD", "forma de respuesta inesperada", response.status);
  }
  return payload;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return isRecord(value) && value["status"] === "ok";
}

export const API_BASE: string =
  (import.meta.env["VITE_API_URL"] as string | undefined) ?? "";

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>(`${API_BASE}/api/health`, isHealthResponse);
}

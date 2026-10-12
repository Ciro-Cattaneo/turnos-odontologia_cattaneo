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

export interface HealthResponse {
  status: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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

function isHealthResponse(value: unknown): value is HealthResponse {
  return isRecord(value) && value["status"] === "ok";
}

const API_BASE: string =
  (import.meta.env["VITE_API_URL"] as string | undefined) ?? "";

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>(`${API_BASE}/api/health`, isHealthResponse);
}

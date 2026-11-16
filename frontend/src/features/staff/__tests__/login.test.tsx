/**
 * Login staff y logout (capa: integración, router en memoria, fetch de borde).
 * # AC frontend-agenda-staff/Sesión staff — login válido, 401 genérico,
 * 400 por campo, 429 con Retry-After y logout con error.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../App";
import { API_BASE } from "../../../shared/api/client";

const meRecepcion = {
  email: "recepcion@ficticio.test",
  rol: "recepcion",
  profesional_id: null,
};
const profesionalesVacios = { items: [], next_cursor: null };

function json(
  payload: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp(initial: string): void {
  const router = createMemoryRouter(appRoutes, { initialEntries: [initial] });
  render(<RouterProvider router={router} />);
}

function completar(email: string, password: string): void {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("Contraseña"), {
    target: { value: password },
  });
}

function enviar(): void {
  fireEvent.click(screen.getByRole("button", { name: /ingresar/i }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("login staff", () => {
  it("test_login_valido_navega_a_agenda", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(
      json({ email: "recepcion@ficticio.test", rol: "recepcion" }),
    );
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));

    renderApp("/staff/login");
    completar("recepcion@ficticio.test", "secreto-ficticio");
    enviar();

    expect(
      await screen.findByRole("heading", { name: /^agenda$/i }),
    ).toBeDefined();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE}/api/auth/login`,
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.body),
    ) as unknown;
    expect(body).toEqual({
      email: "recepcion@ficticio.test",
      password: "secreto-ficticio",
    });
  });

  it("test_login_401_muestra_mensaje_generico_y_conserva_valores", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json({ detail: "Credenciales inválidas" }, 401));

    renderApp("/staff/login");
    completar("nadie@ficticio.test", "incorrecta");
    enviar();

    expect(await screen.findByText(/credenciales inválidas/i)).toBeDefined();
    expect(
      (screen.getByLabelText("Email") as HTMLInputElement).value,
    ).toBe("nadie@ficticio.test");
    expect(
      (screen.getByLabelText("Contraseña") as HTMLInputElement).value,
    ).toBe("incorrecta");
    expect(screen.queryByRole("heading", { name: /^agenda$/i })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["email", "Ingresá un email válido"],
    ["password", "La contraseña es obligatoria"],
  ])(
    "test_login_400_marca_campo_%s_y_conserva_lo_ingresado",
    async (campo, mensaje) => {
      const fetchMock = stubFetch();
      fetchMock.mockResolvedValueOnce(
        json(
          {
            detail: [
              { campo: `body.${campo}`, error: mensaje, tipo: "value_error" },
            ],
          },
          400,
        ),
      );

      renderApp("/staff/login");
      completar("recepcion@ficticio.test", "secreto-ficticio");
      enviar();

      expect(await screen.findByText(mensaje)).toBeDefined();
      const email = screen.getByLabelText("Email");
      const password = screen.getByLabelText("Contraseña");
      expect(email.getAttribute("aria-invalid")).toBe(
        campo === "email" ? "true" : "false",
      );
      expect(password.getAttribute("aria-invalid")).toBe(
        campo === "password" ? "true" : "false",
      );
      expect((email as HTMLInputElement).value).toBe("recepcion@ficticio.test");
      expect((password as HTMLInputElement).value).toBe("secreto-ficticio");
      expect(screen.queryByRole("heading", { name: /^agenda$/i })).toBeNull();
    },
  );

  it("test_login_429_indica_la_espera_sin_reintentar", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(
      json({ detail: "Demasiados intentos" }, 429, { "Retry-After": "30" }),
    );

    renderApp("/staff/login");
    completar("recepcion@ficticio.test", "secreto-ficticio");
    enviar();

    expect(await screen.findByText(/30 segundos/i)).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("test_logout_exitoso_limpia_sesion_y_vuelve_a_login", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));
    fetchMock.mockResolvedValueOnce(json({ ok: true }));

    renderApp("/staff/agenda");
    await screen.findByRole("heading", { name: /^agenda$/i });
    fireEvent.click(screen.getByRole("button", { name: /cerrar sesión/i }));

    expect(
      await screen.findByRole("heading", { name: /iniciar sesión/i }),
    ).toBeDefined();
    expect(screen.queryByText("recepcion@ficticio.test")).toBeNull();
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${API_BASE}/api/auth/logout`,
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("test_logout_fallido_muestra_error_y_conserva_sesion", async () => {
    const fetchMock = stubFetch();
    fetchMock.mockResolvedValueOnce(json(meRecepcion));
    fetchMock.mockResolvedValueOnce(json(profesionalesVacios));
    fetchMock.mockResolvedValueOnce(json({ detail: "falla interna" }, 500));

    renderApp("/staff/agenda");
    await screen.findByRole("heading", { name: /^agenda$/i });
    fireEvent.click(screen.getByRole("button", { name: /cerrar sesión/i }));

    expect(await screen.findByText(/no pudimos completar/i)).toBeDefined();
    expect(screen.getByText("recepcion@ficticio.test")).toBeDefined();
    expect(screen.queryByRole("heading", { name: /iniciar sesión/i })).toBeNull();
  });
});

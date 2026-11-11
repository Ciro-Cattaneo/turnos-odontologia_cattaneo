/** Flujo público de reserva (capa: integración, fetch mockeado en el borde). */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  useLocation,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Home } from "../Home";
import { NotFound } from "../NotFound";
import { Reservar } from "../Reservar";

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const fetchMock = vi.fn<FetchLike>();

const PROF_ID = "11111111-1111-4111-8111-111111111111";
const TURNO_ID = "22222222-2222-4222-8222-222222222222";
const TOKEN = "33333333-3333-4333-8333-333333333333";
const FECHA = "2026-11-10";

const valoresPaciente = {
  nombre: "Paciente Ficticio Test",
  dni: "30000001",
  telefono: "1100000001",
  obra_social: "Obra Social Test",
  email: "paciente@ejemplo.test",
};

const profesionalesPage = {
  items: [
    {
      id: PROF_ID,
      nombre: "Dra. Ficticia Test",
      especialidad: "Odontología",
      matricula: "MP-0000",
      duracion_default_min: 30,
      ultima_actualizacion: null,
    },
  ],
  next_cursor: null,
};

const disponibilidadPage = {
  profesional_id: PROF_ID,
  slots: [
    {
      inicio: "2026-11-10T09:00:00-03:00",
      fin: "2026-11-10T09:30:00-03:00",
      duracion_min: 30,
    },
  ],
  ultima_actualizacion: null,
};

const turnoCreado = {
  id: TURNO_ID,
  estado: "reservado",
  inicio: "2026-11-10T09:00:00-03:00",
  fin: "2026-11-10T09:30:00-03:00",
  duracion_min: 30,
  profesional: { id: PROF_ID, nombre: "Dra. Ficticia Test" },
  paciente: {
    nombre: valoresPaciente.nombre,
    dni: valoresPaciente.dni,
    email: valoresPaciente.email,
  },
  token_cancelacion: TOKEN,
  cancel_url: `/cancelar?token=${TOKEN}&id=${TURNO_ID}`,
  notificaciones_encoladas: true,
};

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function Ubicacion(): JSX.Element {
  const location = useLocation();
  return <output data-testid="ubicacion">{location.pathname}</output>;
}

type MemoryRouterInstance = ReturnType<typeof createMemoryRouter>;

function renderApp(path: string): MemoryRouterInstance {
  const router = createMemoryRouter(
    [
      { path: "/", element: <Home /> },
      { path: "/reservar", element: <Reservar /> },
      { path: "*", element: <NotFound /> },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

async function elegirProfesionalYFecha(): Promise<void> {
  await screen.findByRole("option", { name: /Dra\. Ficticia Test/ });
  fireEvent.change(screen.getByLabelText("Profesional"), {
    target: { value: PROF_ID },
  });
  fireEvent.change(screen.getByLabelText("Fecha"), {
    target: { value: FECHA },
  });
  fireEvent.click(screen.getByRole("button", { name: "Buscar horarios" }));
  await screen.findByRole("button", { name: "09:00 a 09:30, 30 min" });
}

function abrirFormulario(): void {
  fireEvent.click(screen.getByRole("button", { name: "09:00 a 09:30, 30 min" }));
}

function completarFormulario(): void {
  fireEvent.change(screen.getByLabelText("Nombre y apellido"), {
    target: { value: valoresPaciente.nombre },
  });
  fireEvent.change(screen.getByLabelText("DNI"), {
    target: { value: valoresPaciente.dni },
  });
  fireEvent.change(screen.getByLabelText("Teléfono"), {
    target: { value: valoresPaciente.telefono },
  });
  fireEvent.change(screen.getByLabelText("Obra social"), {
    target: { value: valoresPaciente.obra_social },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: valoresPaciente.email },
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("página /reservar", () => {
  it("test_reserva_feliz_201", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(jsonResponse(turnoCreado, 201));

    renderApp("/reservar");
    await elegirProfesionalYFecha();
    abrirFormulario();
    completarFormulario();
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(await screen.findByText(/reserva confirmada/i)).toBeDefined();
    expect(screen.getByText("Dra. Ficticia Test")).toBeDefined();
    expect(screen.getByText("30 min")).toBeDefined();
    const link = screen.getByRole("link", { name: /cancelar turno/i });
    expect(link.getAttribute("href")).toBe(`/cancelar?token=${TOKEN}&id=${TURNO_ID}`);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("test_reserva_400_por_campo", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: [
              {
                campo: "paciente.email",
                error: "El mail fue rechazado por el servidor",
                tipo: "value_error",
              },
            ],
          },
          400,
        ),
      );

    renderApp("/reservar");
    await elegirProfesionalYFecha();
    abrirFormulario();
    completarFormulario();
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(
      await screen.findByText("El mail fue rechazado por el servidor"),
    ).toBeDefined();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe(
      "true",
    );
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
      valoresPaciente.email,
    );
    expect(screen.queryByText(/reserva confirmada/i)).toBeNull();
  });

  it("test_reserva_409_con_alternativos", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: {
              codigo: "slot_ocupado",
              alternativos: [
                {
                  inicio: "2026-11-10T10:00:00-03:00",
                  fin: "2026-11-10T10:30:00-03:00",
                  duracion_min: 30,
                },
              ],
            },
          },
          409,
        ),
      );

    renderApp("/reservar");
    await elegirProfesionalYFecha();
    abrirFormulario();
    completarFormulario();
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(await screen.findByText(/ese horario se ocupó/i)).toBeDefined();
    const alternativo = screen.getByRole("button", { name: "10:00 a 10:30" });
    fireEvent.click(alternativo);

    expect(screen.getByText(/10:00–10:30/)).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe(valoresPaciente.nombre);
    expect(screen.queryByText(/reserva confirmada/i)).toBeNull();
  });

  it("test_reserva_error_de_red_con_reintento", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(profesionalesPage));

    renderApp("/reservar");

    expect(await screen.findByText(/no pudimos conectarnos/i)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(
      await screen.findByRole("option", { name: /Dra\. Ficticia Test/ }),
    ).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("test_reserva_respuesta_inesperada_es_error", async () => {
    fetchMock.mockResolvedValueOnce(new Response("no-json", { status: 200 }));

    renderApp("/reservar");

    expect(
      await screen.findByText(/la respuesta del servidor no es válida/i),
    ).toBeDefined();
    expect(screen.queryByRole("option")).toBeNull();
  });

  it("test_reserva_404_profesional_conserva_formulario", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(jsonResponse({ detail: "No encontrado" }, 404));

    renderApp("/reservar");
    await elegirProfesionalYFecha();
    abrirFormulario();
    completarFormulario();
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(
      await screen.findByText(/el profesional ya no está disponible/i),
    ).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe(valoresPaciente.nombre);
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
      valoresPaciente.email,
    );
  });

  it("test_reserva_429_post_turnos_muestra_espera", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "Demasiadas reservas" }, 429, {
          "Retry-After": "7",
        }),
      );

    renderApp("/reservar");
    await elegirProfesionalYFecha();
    abrirFormulario();
    completarFormulario();
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(await screen.findByText(/demasiados intentos/i)).toBeDefined();
    expect(screen.getByText(/7 segundos/i)).toBeDefined();
    expect(
      (screen.getByLabelText("Nombre y apellido") as HTMLInputElement).value,
    ).toBe(valoresPaciente.nombre);
  });

  it("test_profesionales_429_muestra_espera", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Demasiadas consultas" }, 429, {
        "Retry-After": "5",
      }),
    );

    renderApp("/reservar");

    expect(await screen.findByText(/demasiados intentos/i)).toBeDefined();
    expect(screen.getByText(/5 segundos/i)).toBeDefined();
  });

  it("test_reserva_no_expone_datos_en_url", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profesionalesPage))
      .mockResolvedValueOnce(jsonResponse(disponibilidadPage))
      .mockResolvedValueOnce(jsonResponse(turnoCreado, 201));

    const router = renderApp("/reservar");
    const urlReservar = (): string =>
      `${router.state.location.pathname}${router.state.location.search}`;

    await elegirProfesionalYFecha();
    expect(urlReservar()).toBe("/reservar");

    abrirFormulario();
    completarFormulario();
    expect(urlReservar()).toBe("/reservar");

    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));
    expect(await screen.findByText(/reserva confirmada/i)).toBeDefined();

    const url = urlReservar();
    expect(url).toBe("/reservar");
    for (const valor of Object.values(valoresPaciente)) {
      expect(url).not.toContain(valor);
    }

    const location = "/reservar";
    cleanup();
    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(jsonResponse(profesionalesPage));
    renderApp(location);

    await screen.findByRole("option", { name: /Dra\. Ficticia Test/ });
    expect(screen.queryByText(/reserva confirmada/i)).toBeNull();
    for (const valor of Object.values(valoresPaciente)) {
      expect(screen.queryByText(valor)).toBeNull();
    }
  });

  it("test_landing_cta_navega_a_reservar", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(profesionalesPage));

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/reservar" element={<Reservar />} />
        </Routes>
        <Ubicacion />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /reservar turno/i }));

    await waitFor(() => {
      expect(screen.getByTestId("ubicacion").textContent).toBe("/reservar");
    });
    expect(
      await screen.findByRole("heading", { name: /reservar turno/i }),
    ).toBeDefined();
  });

  it("test_landing_no_pide_login", () => {
    renderApp("/");

    expect(screen.queryByLabelText(/contraseña/i)).toBeNull();
    expect(screen.queryByText(/iniciar sesión/i)).toBeNull();
    expect(screen.queryByText(/usuario/i)).toBeNull();
    expect(screen.getByRole("link", { name: /reservar turno/i })).toBeDefined();
  });
});

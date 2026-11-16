import { useRoutes, type RouteObject } from "react-router-dom";

import { StaffLayout } from "./features/staff/components/StaffLayout";
import { AgendaPage } from "./features/staff/pages/AgendaPage";
import { LoginPage } from "./features/staff/pages/LoginPage";
import { NotificacionesPage } from "./features/staff/pages/NotificacionesPage";
import { Cancelar } from "./pages/Cancelar";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { Reservar } from "./pages/Reservar";

export const appRoutes: RouteObject[] = [
  { path: "/", element: <Home /> },
  { path: "/reservar", element: <Reservar /> },
  { path: "/cancelar", element: <Cancelar /> },
  { path: "/staff/login", element: <LoginPage /> },
  {
    path: "/staff",
    element: <StaffLayout />,
    children: [
      { path: "agenda", element: <AgendaPage /> },
      { path: "notificaciones", element: <NotificacionesPage /> },
    ],
  },
  { path: "*", element: <NotFound /> },
];

export function App(): JSX.Element {
  return <>{useRoutes(appRoutes)}</>;
}

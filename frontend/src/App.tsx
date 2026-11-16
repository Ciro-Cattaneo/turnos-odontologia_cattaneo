import { useRoutes, type RouteObject } from "react-router-dom";

import { AdminProfesionalesPage } from "./features/staff/admin/pages/AdminProfesionalesPage";
import { AdminReportesPage } from "./features/staff/admin/pages/AdminReportesPage";
import { AdminUsuariosPage } from "./features/staff/admin/pages/AdminUsuariosPage";
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
      { path: "admin/profesionales", element: <AdminProfesionalesPage /> },
      { path: "admin/usuarios", element: <AdminUsuariosPage /> },
      { path: "admin/reportes", element: <AdminReportesPage /> },
    ],
  },
  { path: "*", element: <NotFound /> },
];

export function App(): JSX.Element {
  return <>{useRoutes(appRoutes)}</>;
}

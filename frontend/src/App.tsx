import { Route, Routes } from "react-router-dom";

import { Cancelar } from "./pages/Cancelar";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { Reservar } from "./pages/Reservar";

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/reservar" element={<Reservar />} />
      <Route path="/cancelar" element={<Cancelar />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

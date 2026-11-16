/**
 * Aislamiento de DOM entre tests (Testing Library no auto-registra sin globals)
 * y compatibilidad jsdom/undici: React Router 6 (data router) construye un
 * `Request` con el `AbortSignal` de jsdom, que Node 24 (undici) rechaza. En
 * tests no hay fetch real (siempre en el borde), así que se descarta la señal.
 */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

const RequestBase = globalThis.Request;

class RequestSinSenalJsdom extends RequestBase {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init === undefined || init.signal === undefined || init.signal === null) {
      super(input, init);
      return;
    }
    const sinSenal: RequestInit = { ...init };
    delete sinSenal.signal;
    super(input, sinSenal);
  }
}

globalThis.Request = RequestSinSenalJsdom;

afterEach(() => {
  cleanup();
});

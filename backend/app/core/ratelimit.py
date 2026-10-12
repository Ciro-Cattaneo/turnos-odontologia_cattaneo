"""Throttling in-process por IP para el login (C-03 D-4).

Ventana deslizante en memoria: blunta credential stuffing sin lockout
permanente (un lockout sería auto-denegación para un mostrador de 3
personas). Topología single-process v1: se resetea en cada deploy y es por
proceso — aceptado en design; migra a Redis con el resto (PB-03).
Límite + ventana fijos aquí: 10 intentos/min/IP.
"""

import time

LOGIN_LIMIT = 10
LOGIN_WINDOW_S = 60

_hits: dict[str, list[float]] = {}


def _prune(key: str, now: float, window_s: int) -> list[float]:
    """Descarta marcas fuera de la ventana (conjunto acotado)."""
    vivas = [t for t in _hits.get(key, []) if now - t < window_s]
    if vivas:
        _hits[key] = vivas
    else:
        _hits.pop(key, None)
    return vivas


def check_rate_limit(key: str) -> bool:
    """True si el intento pasa; False si excede (llamar ANTES de autenticar)."""
    return check_rate_limit_with(key, LOGIN_LIMIT, LOGIN_WINDOW_S)


def check_rate_limit_with(key: str, limit: int, window_s: int) -> bool:
    """Variante parametrizable (tests fijan límite/ventana sin dormir)."""
    now = time.monotonic()
    vivas = _prune(key, now, window_s)
    if len(vivas) >= limit:
        return False
    vivas.append(now)
    _hits[key] = vivas
    return True


def reset() -> None:
    """Limpia el estado (tests; en prod el prune perezoso alcanza)."""
    _hits.clear()
    _public.clear()


# --- Límite público C-04 D-5: 30 req/min/IP, ventana fija 60s (anti-scraping
# RN-AU-03). En-proceso v1 (single-host); `REDIS_URL` solo documentada para
# escalar (PB-03) — ver `Settings.REDIS_URL`. Reloj inyectable en tests
# (fake clock, sin sleeps).

PUBLIC_LIMIT = 30
PUBLIC_WINDOW_S = 60

# key -> (inicio_ventana_monotonic, conteo_en_ventana).
_public: dict[str, tuple[float, int]] = {}


def check_public_rate_limit(
    key: str,
    *,
    now: float | None = None,
    limit: int = PUBLIC_LIMIT,
    window_s: int = PUBLIC_WINDOW_S,
) -> tuple[bool, float]:
    """Ventana fija: `(pasa, retry_after_s)`.

    `retry_after_s` es 0 si pasa; si no, segundos hasta el reset de la ventana.
    """
    t = time.monotonic() if now is None else now
    inicio, conteo = _public.get(key, (t, 0))
    if t - inicio >= window_s:
        inicio, conteo = t, 0
    if conteo >= limit:
        return False, (inicio + window_s) - t
    _public[key] = (inicio, conteo + 1)
    return True, 0.0


def reset_public() -> None:
    """Limpia solo el estado público (tests)."""
    _public.clear()

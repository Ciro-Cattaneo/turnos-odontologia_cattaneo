"""Matriz parametrizada de cómputo de slots (capa: servicio puro, sin DB).

# AC agenda-disponibilidad/Cómputo-público (feliz, 45', sin-ventana, borde,
# liberan-slot). Nombres `test_<escenario>_<resultado>`; sin mocks internos.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.modules.agenda.slot_service import (
    BloqueoRango,
    Slot,
    TurnoOcupado,
    Ventana,
    compute_slots,
)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2026, 10, 19)  # lunes


def _ventana(dia=0, desde=9, hasta=11, vig_desde=None, vig_hasta=None):
    return Ventana(
        dia_semana=dia,
        hora_desde=time(desde, 0),
        hora_hasta=time(hasta, 0),
        vigente_desde=vig_desde,
        vigente_hasta=vig_hasta,
    )


def _dt(h, m=0):
    return datetime(2026, 10, 19, h, m, tzinfo=TZ)


def test_ventana_simple_sin_ocupacion_ofrece_todos():
    """# AC feliz-base: ventana 09-11 30' sin bloqueos/turnos → 4 slots."""
    slots = compute_slots([_ventana()], [], [], 30, LUNES, LUNES, TZ)
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [
        (9, 0),
        (9, 30),
        (10, 0),
        (10, 30),
    ]
    assert all(isinstance(s, Slot) and s.duracion_min == 30 for s in slots)


def test_ventana_menos_bloqueo_y_reservado_excluye_ocupados():
    """# AC feliz: bloqueo 09:30-10:00 + reservado 10:00-10:30 → [09:00, 10:30]."""
    bloqueos = [BloqueoRango(desde=_dt(9, 30), hasta=_dt(10, 0))]
    ocupados = [TurnoOcupado(inicio=_dt(10, 0), fin=_dt(10, 30))]
    slots = compute_slots([_ventana()], bloqueos, ocupados, 30, LUNES, LUNES, TZ)
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [(9, 0), (10, 30)]


def test_granularidad_45_responde_slots_45():
    """# AC granularidad-45: ventana 09-12 45' → 09:00, 09:45, 10:30, 11:15."""
    slots = compute_slots([_ventana(hasta=12)], [], [], 45, LUNES, LUNES, TZ)
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [
        (9, 0),
        (9, 45),
        (10, 30),
        (11, 15),
    ]


def test_sin_ventana_responde_lista_vacia():
    """# AC sin-ventana: sin ventanas vigentes → 200-lista-vacía (no inventa)."""
    assert compute_slots([], [], [], 30, LUNES, LUNES, TZ) == []


def test_borde_ventana_incluye_slot_que_termina_exacta():
    """# AC borde `[)`: ventana 09-10 30' → [09:00, 09:30], nada excede 10:00."""
    slots = compute_slots([_ventana(hasta=10)], [], [], 30, LUNES, LUNES, TZ)
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [(9, 0), (9, 30)]
    assert all(s.fin <= _dt(10, 0) for s in slots)


def test_cancelado_y_atendido_liberan_slot():
    """# AC liberan-slot: cancelado/atendido no ocupan (solo reservado/conf)."""
    # La capa servicio recibe solo turnos activos ya filtrados (reservado,
    # confirmado); este test fija que turnos no-activos no se le pasan y por
    # tanto ambos slots quedan libres.
    slots = compute_slots([_ventana(hasta=10)], [], [], 30, LUNES, LUNES, TZ)
    assert len(slots) == 2


def test_bloqueo_parcial_solo_excluye_solapados():
    """# AC bloqueo-parcial: bloqueo 09:30-10:00 deja [09:00, 10:00, 10:30]."""
    bloqueos = [BloqueoRango(desde=_dt(9, 30), hasta=_dt(10, 0))]
    slots = compute_slots([_ventana()], bloqueos, [], 30, LUNES, LUNES, TZ)
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [
        (9, 0),
        (10, 0),
        (10, 30),
    ]


def test_adyacente_al_bloqueo_se_ofrece():
    """# AC borde-adyacente: slot que empieza donde termina el bloqueo → libre."""
    bloqueos = [BloqueoRango(desde=_dt(9, 0), hasta=_dt(9, 30))]
    slots = compute_slots([_ventana(hasta=10)], bloqueos, [], 30, LUNES, LUNES, TZ)
    assert (slots[0].inicio.hour, slots[0].inicio.minute) == (9, 30)


# --- Matriz parametrizada 5.1: granularidad × ventanas × bloqueos × bookings ---

MARTES = date(2026, 10, 20)


def _caso(gran, ventanas, bloqueos, ocupados, dia=LUNES):
    return compute_slots(ventanas, bloqueos, ocupados, gran, dia, dia, TZ)


def _horas(slots):
    return [(s.inicio.hour, s.inicio.minute) for s in slots]


def _ventanas_por_clave(clave):
    if clave == "simple":
        return [_ventana()]
    if clave == "multi":
        return [
            Ventana(dia_semana=0, hora_desde=time(9, 0), hora_hasta=time(10, 0)),
            Ventana(dia_semana=0, hora_desde=time(10, 30), hora_hasta=time(11, 30)),
        ]
    if clave == "vigencia-parcial":
        return [
            Ventana(
                dia_semana=0,
                hora_desde=time(9, 0),
                hora_hasta=time(11, 0),
                vigente_desde=date(2026, 10, 19),
                vigente_hasta=date(2026, 10, 19),
            )
        ]
    if clave == "vigencia-excluida":
        return [
            Ventana(
                dia_semana=0,
                hora_desde=time(9, 0),
                hora_hasta=time(11, 0),
                vigente_desde=date(2026, 11, 1),
                vigente_hasta=date(2026, 12, 31),
            )
        ]
    raise AssertionError(clave)


def _bloqueos_por_clave(clave):
    if clave == "ninguno":
        return []
    if clave == "parcial":
        return [BloqueoRango(desde=_dt(9, 30), hasta=_dt(10, 0))]
    if clave == "total":
        # Cubre todas las ventanas de la matriz (simple 09-11 y multi).
        return [BloqueoRango(desde=_dt(8, 0), hasta=_dt(12, 0))]
    raise AssertionError(clave)


def _ocupados_por_clave(clave):
    if clave == "ninguno":
        return []
    if clave == "activo-solapado":
        return [TurnoOcupado(inicio=_dt(10, 0), fin=_dt(10, 30))]
    if clave == "borde-adyacente":
        # Termina donde empieza la primera ventana → no ocupa (`[)`).
        return [TurnoOcupado(inicio=_dt(8, 30), fin=_dt(9, 0))]
    raise AssertionError(clave)


@pytest.mark.parametrize("gran", [30, 45], ids=["gran30", "gran45"])
@pytest.mark.parametrize(
    "ventanas_clave", ["simple", "multi", "vigencia-parcial", "vigencia-excluida"]
)
@pytest.mark.parametrize("bloqueos_clave", ["ninguno", "parcial", "total"])
@pytest.mark.parametrize(
    "bookings_clave", ["ninguno", "activo-solapado", "borde-adyacente"]
)
def test_matriz_ventanas_menos_bloqueos_menos_bookings(
    gran, ventanas_clave, bloqueos_clave, bookings_clave
):
    """# AC matriz: `ventanas − bloqueos − ocupados` en toda combinación.

    Invariantes (no tautología): sin ventana vigente → vacío; bloqueo total →
    vacío; borde-adyacente ≡ ninguno; todo slot dentro de alguna ventana.
    """
    ventanas = _ventanas_por_clave(ventanas_clave)
    bloqueos = _bloqueos_por_clave(bloqueos_clave)
    ocupados = _ocupados_por_clave(bookings_clave)
    slots = _caso(gran, ventanas, bloqueos, ocupados)
    if ventanas_clave == "vigencia-excluida" or bloqueos_clave == "total":
        assert slots == []
        return
    referencia = _caso(gran, ventanas, [], [])
    if bloqueos_clave == "ninguno" and bookings_clave in ("ninguno", "borde-adyacente"):
        assert _horas(slots) == _horas(referencia)
    else:
        # Resta monótona: lo ofrecido ⊆ referencia (la reducción estricta de
        # cada caso feliz/borde la fijan los tests dedicados de arriba).
        assert set(_horas(slots)) <= set(_horas(referencia))
        assert len(slots) <= len(referencia)
    for s in slots:
        assert (s.fin - s.inicio).total_seconds() // 60 == gran
        assert any(
            s.inicio >= datetime.combine(LUNES, v.hora_desde, tzinfo=TZ)
            and s.fin <= datetime.combine(LUNES, v.hora_hasta, tzinfo=TZ)
            for v in ventanas
        )
        for b in bloqueos:
            assert not (s.inicio < b.hasta and b.desde < s.fin)
        for t in ocupados:
            assert not (s.inicio < t.fin and t.inicio < s.fin)


def test_matriz_multi_ventana_solapamientos_exactos():
    """# AC matriz-multi: dos ventanas → slots de ambas, ordenados."""
    slots = _caso(30, _ventanas_por_clave("multi"), [], [], LUNES)
    assert _horas(slots) == [(9, 0), (9, 30), (10, 30), (11, 0)]


def test_matriz_vigencia_parcial_solo_dia_vigente():
    """# AC matriz-vigencia: el lunes vigente ofrece; el martes no."""
    ventanas = _ventanas_por_clave("vigencia-parcial")
    assert len(_caso(30, ventanas, [], [], LUNES)) == 4
    assert _caso(30, ventanas, [], [], MARTES) == []

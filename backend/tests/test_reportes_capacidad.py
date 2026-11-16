"""Capacidad ofrecible del reporte (capa: unit, puro — sin DB).

# AC RE-R2: la capacidad es la grilla real de `compute_slots` sin turnos
# (respeta bloqueos y vigencia, y descuenta el resto no múltiplo).
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.modules.agenda.slot_service import BloqueoRango, Ventana
from app.modules.reportes.service import capacidad_ofrecible

TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# 2026-10-19 es lunes (`dia_semana=0`); 2026-10-26 el lunes siguiente.
LUNES = date(2026, 10, 19)
LUNES_SIGUIENTE = date(2026, 10, 26)


def _ventana(dia_semana=0, desde=(9, 0), hasta=(12, 0), **kw):
    return Ventana(
        dia_semana=dia_semana,
        hora_desde=time(*desde),
        hora_hasta=time(*hasta),
        **kw,
    )


def test_capacidad_ventana_sin_bloqueos_180():
    """# AC RE-R2: ventana 09–12 con default 30' → 6 slots = 180'."""
    total = capacidad_ofrecible([_ventana()], [], 30, LUNES, LUNES, TZ)
    assert total == 180


def test_capacidad_bloqueo_resta_slots():
    """# AC RE-R2: un bloqueo 10–11 descuenta dos slots → 120'."""
    bloqueo = BloqueoRango(
        desde=datetime(2026, 10, 19, 10, 0, tzinfo=TZ),
        hasta=datetime(2026, 10, 19, 11, 0, tzinfo=TZ),
    )
    total = capacidad_ofrecible([_ventana()], [bloqueo], 30, LUNES, LUNES, TZ)
    assert total == 120


def test_capacidad_respeta_vigencia():
    """# AC RE-R2: `vigente_desde` posterior excluye el lunes previo."""
    ventana = _ventana(vigente_desde=date(2026, 10, 20))
    total = capacidad_ofrecible([ventana], [], 30, LUNES, LUNES_SIGUIENTE, TZ)
    assert total == 180


def test_capacidad_sin_ventanas_cero():
    """# AC RE-R2: sin ventanas vigentes la capacidad es cero."""
    assert capacidad_ofrecible([], [], 30, LUNES, LUNES_SIGUIENTE, TZ) == 0


def test_capacidad_ventana_no_multiplo_descuenta_resto():
    """# AC RE-R2: ventana de 50' con default 30' → un slot de 30'."""
    total = capacidad_ofrecible(
        [_ventana(desde=(9, 0), hasta=(9, 50))], [], 30, LUNES, LUNES, TZ
    )
    assert total == 30

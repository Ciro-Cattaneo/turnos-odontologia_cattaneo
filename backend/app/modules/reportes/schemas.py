"""Schemas del reporte de ocupación (C-11 D-8/D-9, regla dura 1).

`ReporteOcupacionQuery` valida el rango en un validador de campo sobre
`hasta` (loc → `campo="hasta"`), no en un validador de modelo genérico.
Tope inclusivo de 366 días (D-16); sin `format`/export (PB-06).
"""

from datetime import date
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
)

Forbid = ConfigDict(extra="forbid")

MAX_RANGO_DIAS = 366


class ReporteOcupacionQuery(BaseModel):
    """Query de `GET /api/reportes/ocupacion` (fechas locales inclusivas)."""

    model_config = Forbid

    desde: date
    hasta: date
    profesional_id: UUID | None = None

    @field_validator("hasta")
    @classmethod
    def _rango_valido(cls, v: date, info: ValidationInfo) -> date:
        desde = info.data.get("desde")
        if desde is None:
            return v
        if v < desde:
            raise ValueError("`hasta` no puede ser anterior a `desde`")
        if (v - desde).days + 1 > MAX_RANGO_DIAS:
            raise ValueError(f"rango máximo {MAX_RANGO_DIAS} días")
        return v


class ProfesionalReporteOut(BaseModel):
    """Identidad mínima del profesional en una fila del reporte."""

    model_config = Forbid

    id: UUID
    nombre: str
    activo: bool


class ReporteFilaOut(BaseModel):
    """Fila de ocupación por profesional."""

    model_config = Forbid

    profesional: ProfesionalReporteOut
    turnos: int
    atendidos: int
    ausentes: int
    cancelados: int
    pendientes: int
    minutos_ocupados: int
    minutos_disponibles: int
    porcentaje_ocupacion: float | None


class ReporteTotalesOut(BaseModel):
    """Suma de los contadores de todas las filas."""

    model_config = Forbid

    turnos: int
    atendidos: int
    ausentes: int
    cancelados: int
    pendientes: int
    minutos_ocupados: int
    minutos_disponibles: int
    porcentaje_ocupacion: float | None


class ReporteOcupacionOut(BaseModel):
    """Respuesta tabular del reporte (items + totales, sin export)."""

    model_config = Forbid

    desde: date
    hasta: date
    zona: str
    items: list[ReporteFilaOut]
    totales: ReporteTotalesOut

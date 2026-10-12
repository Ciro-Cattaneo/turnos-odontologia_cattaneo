"""002_agenda_meta — `ultima_actualizacion` + trigger freshness (C-04 D-2).

Revision ID: 002_agenda_meta

Aditiva: columna nullable (backfill NULL = "sin datos", sin destructivo) +
función/trigger `touch_profesional_updated` en AFTER INSERT/UPDATE/DELETE
sobre `disponibilidad` y `bloqueo`. Downgrade revierte trigger/función/columna.
No toca 001 ni el EXCLUDE de turnos.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_agenda_meta"
down_revision: str | Sequence[str] | None = "001_core_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRIGGER_FN = """CREATE OR REPLACE FUNCTION touch_profesional_updated()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    UPDATE profesional SET ultima_actualizacion = now()
    WHERE id = OLD.profesional_id;
    RETURN OLD;
  ELSE
    UPDATE profesional SET ultima_actualizacion = now()
    WHERE id = NEW.profesional_id;
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql"""

TRIGGER_DISP = """CREATE TRIGGER trg_disponibilidad_touch
AFTER INSERT OR UPDATE OR DELETE ON disponibilidad
FOR EACH ROW EXECUTE FUNCTION touch_profesional_updated()"""

TRIGGER_BLOQ = """CREATE TRIGGER trg_bloqueo_touch
AFTER INSERT OR UPDATE OR DELETE ON bloqueo
FOR EACH ROW EXECUTE FUNCTION touch_profesional_updated()"""


def upgrade() -> None:
    """Agrega columna + función + triggers (backfill implícito NULL)."""
    op.add_column(
        "profesional",
        sa.Column("ultima_actualizacion", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(TRIGGER_FN)
    op.execute(TRIGGER_DISP)
    op.execute(TRIGGER_BLOQ)


def downgrade() -> None:
    """Revierte triggers, función y columna (orden inverso)."""
    op.execute("DROP TRIGGER IF EXISTS trg_bloqueo_touch ON bloqueo")
    op.execute("DROP TRIGGER IF EXISTS trg_disponibilidad_touch ON disponibilidad")
    op.execute("DROP FUNCTION IF EXISTS touch_profesional_updated()")
    op.drop_column("profesional", "ultima_actualizacion")

"""Fixtures compartidas: expone `backend/` en `sys.path` (imports `app.*`)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Env mínimo ficticio para que `app.main` importe en tests (datos ficticios,
# nunca credenciales reales — regla dura 12). Los tests de config usan
# `monkeypatch` para aislar/alterar estas vars por caso.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/turnos")
os.environ.setdefault("SECRET_KEY", "clave-ficticia-solo-tests-0123456789abcdef")
os.environ.setdefault("ADMIN_EMAIL", "admin-ficticio@cattaneo.test")
os.environ.setdefault("ADMIN_PASSWORD", "password-ficticia-solo-tests")
os.environ.setdefault("SMTP_HOST", "smtp.ficticio.test")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "usuario-ficticio")
os.environ.setdefault("SMTP_PASS", "pass-ficticia-solo-tests")
os.environ.setdefault("SMTP_FROM", "turnos@ficticio.test")
os.environ.setdefault("TZ", "America/Argentina/Buenos_Aires")
os.environ.setdefault("FRONTEND_URL", "https://turnos.ficticio.test")

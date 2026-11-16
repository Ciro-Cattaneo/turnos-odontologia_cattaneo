"""Contrato de la imagen y del repo (DO-R1 ERROR, SC-R1; capa archivo/repo)."""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"

_EXTENSIONES_BINARIAS = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".zip",
}
_RUTAS_EXCLUIDAS = ("backend/tests/", "openspec/", "knowledge-base/")
_ARCHIVOS_EXCLUIDOS = {".env.example", "backend/tests/test_deploy_image.py"}

_PATRONES_TOKEN = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
]
_PATRON_CLAVE_VALOR = re.compile(
    r"(?i)\b(SECRET_KEY|SMTP_PASS|ADMIN_PASSWORD|POSTGRES_PASSWORD)"
    r"\s*[=:]\s*[\"']?([^\s\"'#]{12,})"
)
_MARCADORES_FICTICIOS = (
    "changeme",
    "ejemplo",
    "ficticio",
    "example",
    "dummy",
    "test",
    "local",
    "${",
)


def test_dockerfile_multistage_compila_frontend():
    """# AC DO-R1 FELIZ — stage Node compila el frontend hacia `static`."""
    texto = DOCKERFILE.read_text(encoding="utf-8")

    assert re.search(r"^FROM\s+node:20", texto, re.MULTILINE)
    assert "npm ci" in texto
    assert "npm run build" in texto
    assert re.search(r"^COPY\s+--from=\S+\s+\S*dist\s+\./static", texto, re.MULTILINE)
    assert re.search(r"^FROM\s+python:3\.12", texto, re.MULTILINE)


def test_dockerfile_usuario_no_root_y_healthcheck():
    """# AC DO-R1 FELIZ — corre con UID != 0 y sondea `/api/health`."""
    texto = DOCKERFILE.read_text(encoding="utf-8")

    usuarios = re.findall(r"^USER\s+(\S+)", texto, re.MULTILINE)
    assert usuarios, "Dockerfile sin USER: el proceso correría como root"
    assert usuarios[-1] not in {"root", "0"}
    assert re.search(r"^HEALTHCHECK\b", texto, re.MULTILINE)
    assert "/api/health" in texto


def test_dockerfile_no_copia_env_ni_secretos():
    """# AC DO-R1 ERROR — la imagen no embebe `.env` ni credenciales."""
    texto = DOCKERFILE.read_text(encoding="utf-8")

    assert not re.search(r"^COPY\s+.*\.env\b", texto, re.MULTILINE)
    for clave in ("SECRET_KEY", "SMTP_PASS", "ADMIN_PASSWORD"):
        assert not re.search(rf"^(ENV|ARG)\s+{clave}[= ]", texto, re.MULTILINE)


def test_dockerfile_cmd_respeta_port_inyectable():
    """D-2/D-3 — el CMD deja que el PaaS inyecte `PORT`."""
    texto = DOCKERFILE.read_text(encoding="utf-8")

    assert "${PORT:-8000}" in texto


def test_dockerignore_excluye_env_node_modules_git():
    """# AC DO-R1 ERROR — contexto de build sin secretos ni artefactos."""
    lineas = {
        linea.strip()
        for linea in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    }

    for patron in (".env", "frontend/node_modules", "frontend/dist", ".git"):
        assert patron in lineas, f"{patron} falta en .dockerignore"
    assert any("__pycache__" in patron for patron in lineas)
    assert any(".pytest_cache" in patron for patron in lineas)


def test_repo_sin_secretos_reales_en_archivos_versionados():
    """# AC DO-R1 ERROR / SC-R1 — ningún secreto real versionado (regla dura 10)."""
    listado = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    hallazgos: list[str] = []
    for relativo in listado.stdout.splitlines():
        if relativo in _ARCHIVOS_EXCLUIDOS or relativo.startswith(_RUTAS_EXCLUIDAS):
            continue
        if Path(relativo).suffix.lower() in _EXTENSIONES_BINARIAS:
            continue
        texto = (REPO_ROOT / relativo).read_text(encoding="utf-8", errors="ignore")
        for patron in _PATRONES_TOKEN:
            if patron.search(texto):
                hallazgos.append(relativo)
        for match in _PATRON_CLAVE_VALOR.finditer(texto):
            valor = match.group(2).lower()
            if not any(marca in valor for marca in _MARCADORES_FICTICIOS):
                hallazgos.append(f"{relativo} ({match.group(1)})")

    assert not hallazgos, f"posibles secretos reales versionados: {hallazgos}"

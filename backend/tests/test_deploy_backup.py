"""Backup/restore de Postgres (DO-R3; capa proceso/Postgres real).

Los scripts son bash y usan el cliente real de Postgres (`pg_dump`,
`pg_restore`); no se mockea ningún binario. La única dependencia externa es
Git Bash + PostgreSQL client tools en la máquina que corre la suite: si no
están, los tests se saltean con una razón explícita (nunca verde inventado).

Datos ficticios (regla dura 12): las bases scratch se crean y se destruyen
por test; nunca se apunta a la base `turnos` de desarrollo.
"""

import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_postgres.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore_postgres.sh"

_DB_DUMP_RE = re.compile(r"^turnos_\d{8}T\d{6}Z\.dump$")


def _find_bash() -> str | None:
    candidatos = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ]
    for candidato in candidatos:
        if candidato and Path(candidato).exists():
            return str(candidato)
    return None


def _find_pg_bin() -> Path | None:
    exe = shutil.which("pg_dump") or shutil.which("pg_dump.exe")
    if exe:
        return Path(exe).parent
    bases = [
        Path(r"C:\Program Files\PostgreSQL"),
        Path("/usr/lib/postgresql"),
        Path("/opt/homebrew/opt"),
    ]
    for base in bases:
        if not base.exists():
            continue
        for candidato in sorted(base.glob("*/bin"), reverse=True):
            if (candidato / "pg_dump").exists() or (candidato / "pg_dump.exe").exists():
                return candidato
    return None


BASH = _find_bash()
PG_BIN = _find_pg_bin()

if BASH is None or PG_BIN is None:
    pytest.skip(
        "requiere bash y cliente PostgreSQL (pg_dump/pg_restore): "
        f"bash={BASH!r} pg_bin={PG_BIN!r}",
        allow_module_level=True,
    )


def _posix(path: Path) -> str:
    """Path estilo Windows (`C:/dir`) para spawnear binarios nativos."""
    return str(path).replace("\\", "/")


def _msys(path: Path) -> str:
    """Path estilo MSYS (`/c/dir`) para el shell: misma identidad de archivo
    que usa el script al aplicar `chmod` (MSYS ignora permisos POSIX si se
    consulta el mismo archivo con otra forma de path)."""
    texto = str(path)
    if os.name != "nt":
        return texto.replace("\\", "/")
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", texto)
    if match:
        return f"/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}"
    return texto.replace("\\", "/")


def _base_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(PG_BIN) + os.pathsep + env.get("PATH", "")
    for clave in (
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "PGSSLMODE",
    ):
        env.pop(clave, None)
    return env


def _run(
    args: list[str],
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 240,
) -> subprocess.CompletedProcess:
    env = _base_env()
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    return subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _run_backup(
    backup_dir: Path,
    *,
    database_url: str,
    retention_days: int | None = None,
    mode: str = "direct",
    timeout: int = 240,
) -> subprocess.CompletedProcess:
    assert BACKUP_SCRIPT.exists(), f"falta {BACKUP_SCRIPT}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    extra = {
        "BACKUP_DIR": _msys(backup_dir),
        "BACKUP_MODE": mode,
        "DATABASE_URL": database_url,
    }
    if retention_days is not None:
        extra["BACKUP_RETENTION_DAYS"] = str(retention_days)
    return _run([BASH, str(BACKUP_SCRIPT)], extra_env=extra, timeout=timeout)


def _run_restore(
    dump: Path,
    target_url: str,
    *,
    force: bool = False,
    expected_turnos: int | None = None,
    timeout: int = 240,
) -> subprocess.CompletedProcess:
    assert RESTORE_SCRIPT.exists(), f"falta {RESTORE_SCRIPT}"
    args = [BASH, str(RESTORE_SCRIPT), _msys(dump), target_url]
    if force:
        args.append("--force")
    extra = {}
    if expected_turnos is not None:
        extra["EXPECTED_TURNO_COUNT"] = str(expected_turnos)
    return _run(args, extra_env=extra, timeout=timeout)


def _posix_mode(path: Path, *, umask: str | None = None) -> str:
    """Modo POSIX tal como lo ve el runtime del script.

    En NTFS `chmod` no persiste un modo POSIX (sólo el bit read-only) y MSYS
    deriva el modo del umask del proceso que consulta; en Linux el modo es
    dato del inodo. `umask` permite consultar la vista efectiva del deploy.
    """
    comando = f"stat -c %a '{_msys(path)}'"
    if umask is not None:
        comando = f"umask {umask}; {comando}"
    result = _run([BASH, "-c", comando])
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _pg_restore_list(dump: Path) -> subprocess.CompletedProcess:
    pg_restore = PG_BIN / ("pg_restore.exe" if os.name == "nt" else "pg_restore")
    return _run([str(pg_restore), "--list", str(dump)])


# --- Utilidades de bases scratch (nunca tocan `turnos`) ---------------------


def _admin_engine():
    from tests.conftest import _real_database_url

    url = make_url(_real_database_url()).set(database="turnos")
    return sqlalchemy.create_engine(url, isolation_level="AUTOCOMMIT")


def _scratch_url(name: str) -> str:
    from tests.conftest import _real_database_url

    return (
        make_url(_real_database_url())
        .set(database=name)
        .render_as_string(hide_password=False)
    )


def _create_scratch_db() -> str:
    name = f"turnos_bk_{uuid.uuid4().hex[:8]}"
    engine = _admin_engine()
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()
    return name


_REINTENTOS_DROP = 10
_ESPERA_DROP_S = 0.2
_SQLSTATE_DROP_TRANSITORIO = frozenset({"42501", "55006"})


def _drop_scratch_db(name: str) -> None:
    """Borra la base scratch tolerando los fallos transitorios del DROP.

    `DROP DATABASE ... WITH (FORCE)` puede fallar con 42501 si un autovacuum
    worker (superusuario) corre sobre esa base —el rol de la app no puede
    terminarlo— o con 55006 si algo la sigue usando. Ambos duran milisegundos,
    así que se reintenta con una espera corta; cualquier otro error se propaga.
    """
    engine = _admin_engine()
    try:
        for intento in range(_REINTENTOS_DROP):
            try:
                with engine.connect() as conn:
                    sentencia = sqlalchemy.text(
                        f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'
                    )
                    conn.execute(sentencia)
                return
            except sqlalchemy.exc.DBAPIError as exc:
                transitorio = (
                    getattr(exc.orig, "sqlstate", None) in _SQLSTATE_DROP_TRANSITORIO
                )
                if not transitorio or intento == _REINTENTOS_DROP - 1:
                    raise
                time.sleep(_ESPERA_DROP_S)
    finally:
        engine.dispose()


def _alembic_upgrade(url: str) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=dict(os.environ, DATABASE_URL=url),
    )
    assert proc.returncode == 0, proc.stderr


def _counts(url: str) -> tuple[int, str | None]:
    engine = sqlalchemy.create_engine(url)
    try:
        with engine.connect() as conn:
            turnos = conn.execute(
                sqlalchemy.text("SELECT count(*) FROM turno")
            ).scalar()
            revision = conn.execute(
                sqlalchemy.text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
        return int(turnos), revision
    finally:
        engine.dispose()


@pytest.fixture
def scratch_db():
    created: list[str] = []

    def factory() -> tuple[str, str]:
        name = _create_scratch_db()
        created.append(name)
        return name, _scratch_url(name)

    yield factory
    for name in created:
        _drop_scratch_db(name)


# --- 4.1 / 4.2 / 4.3 / 4.7 — backup ---------------------------------------


def test_backup_crea_dump_verificable_permisos_600(pg_test_url, tmp_path):
    """# AC DO-R3 FELIZ — dump custom verificable, nombre UTC y modo 600."""
    backup_dir = tmp_path / "backups"

    result = _run_backup(backup_dir, database_url=pg_test_url)

    assert result.returncode == 0, result.stderr
    dumps = sorted(backup_dir.glob("turnos_*.dump"))
    assert len(dumps) == 1, [d.name for d in dumps]
    dump = dumps[0]
    assert _DB_DUMP_RE.match(dump.name), dump.name
    assert dump.stat().st_size > 0
    assert _pg_restore_list(dump).returncode == 0
    if os.name == "nt":
        # NTFS no conserva modos POSIX; se valida la vista efectiva con el
        # umask de deploy + el contrato literal del script (en Linux se
        # verifica el modo real del inodo debajo).
        assert _posix_mode(dump, umask="077") == "600"
        contrato = BACKUP_SCRIPT.read_text(encoding="utf-8")
        assert "umask 077" in contrato
        assert 'chmod 600 "$tmp"' in contrato
    else:
        assert stat.S_IMODE(dump.stat().st_mode) == 0o600
    assert not list(backup_dir.glob("*.tmp"))


def test_backup_dos_corridas_timestamps_unicos_sin_sobrescribir(pg_test_url, tmp_path):
    """# AC DO-R3 BORDE — dos corridas no se pisan ni se sobrescriben."""
    backup_dir = tmp_path / "backups"

    primera = _run_backup(backup_dir, database_url=pg_test_url)
    assert primera.returncode == 0, primera.stderr
    time.sleep(1.1)
    segunda = _run_backup(backup_dir, database_url=pg_test_url)
    assert segunda.returncode == 0, segunda.stderr

    dumps = sorted(backup_dir.glob("turnos_*.dump"))
    assert len(dumps) == 2, [d.name for d in dumps]
    assert dumps[0].name != dumps[1].name
    assert all(_DB_DUMP_RE.match(d.name) for d in dumps)
    assert all(d.stat().st_size > 0 for d in dumps)
    for dump in dumps:
        assert _pg_restore_list(dump).returncode == 0


@pytest.mark.parametrize("retention_days", [7, 1])
def test_backup_rota_dumps_mayores_a_7_dias(pg_test_url, tmp_path, retention_days):
    """# AC DO-R3 BORDE — el dump de 8 días se borra, el reciente queda."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)

    viejo = backup_dir / "turnos_20200101T030000Z.dump"
    viejo.write_bytes(b"dump-viejo-ficticio")
    ahora = time.time()
    os.utime(viejo, (ahora - 8 * 86400, ahora - 8 * 86400))
    reciente = backup_dir / "turnos_20261116T030000Z.dump"
    reciente.write_bytes(b"dump-reciente-ficticio")

    result = _run_backup(
        backup_dir,
        database_url=pg_test_url,
        retention_days=retention_days,
    )

    assert result.returncode == 0, result.stderr
    assert not viejo.exists()
    assert reciente.exists()
    assert len(list(backup_dir.glob("turnos_*.dump"))) == 2


def test_backup_falla_db_inalcanzable_exit_no_cero_sin_dump_parcial(tmp_path):
    """# AC DO-R3 ERROR — DB inalcanzable ⇒ exit ≠ 0 y ningún dump."""
    backup_dir = tmp_path / "backups"
    url = "postgresql+psycopg://turnos:clave-ficticia@127.0.0.1:1/turnos"

    result = _run_backup(backup_dir, database_url=url, timeout=60)

    assert result.returncode != 0
    assert list(backup_dir.glob("turnos_*.dump")) == []
    assert list(backup_dir.glob("*.tmp")) == []


def test_backup_error_no_expone_password_ni_dsn(tmp_path):
    """# AC DO-R3 ERROR — el error no imprime password ni DSN completo."""
    backup_dir = tmp_path / "backups"
    password = "s3cr3t-ficticia-no-filtrar"
    url = f"postgresql+psycopg://turnos:{password}@127.0.0.1:1/turnos"

    result = _run_backup(backup_dir, database_url=url, timeout=60)

    assert result.returncode != 0
    salida = result.stdout + result.stderr
    assert password not in salida
    assert url not in salida
    assert f"turnos:{password}" not in salida


def test_backup_no_deja_archivos_tmp_y_es_idempotente_en_nombres(pg_test_url, tmp_path):
    """# AC DO-R3 BORDE — tras dos corridas no queda ningún `.tmp`."""
    backup_dir = tmp_path / "backups"

    for _ in range(2):
        result = _run_backup(backup_dir, database_url=pg_test_url)
        assert result.returncode == 0, result.stderr
        time.sleep(1.1)

    assert not list(backup_dir.rglob("*.tmp"))
    nombres = [d.name for d in backup_dir.glob("turnos_*.dump")]
    assert len(nombres) == 2
    assert len(set(nombres)) == 2


def test_backup_modo_compose_documentado_sin_password_en_argv():
    """# AC DO-R3 — `BACKUP_MODE=compose` existe y no pasa secretos por argv."""
    contrato = BACKUP_SCRIPT.read_text(encoding="utf-8")

    assert "BACKUP_MODE" in contrato
    assert "docker compose exec -T db pg_dump" in contrato
    linea_compose = next(
        linea
        for linea in contrato.splitlines()
        if "docker compose exec -T db pg_dump" in linea
    )
    assert "PGPASSWORD" not in linea_compose
    assert "--password" not in contrato


# --- 4.5 — restore --------------------------------------------------------


def _seed_source_db(url: str, turnos: int = 3) -> None:
    from tests.conftest import mk_paciente, mk_profesional, mk_turno

    _alembic_upgrade(url)
    engine = sqlalchemy.create_engine(url)
    base = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)
    try:
        with Session(engine) as session:
            profesional = mk_profesional(session)
            paciente = mk_paciente(session)
            for i in range(turnos):
                inicio = base + timedelta(hours=i)
                mk_turno(
                    session,
                    profesional.id,
                    paciente.id,
                    inicio=inicio,
                    fin=inicio + timedelta(minutes=30),
                )
            session.commit()
    finally:
        engine.dispose()


def test_restore_reproduce_conteos_de_turnos_y_revision(tmp_path, scratch_db):
    """# AC DO-R3 FELIZ — el restore reproduce conteos y revisión Alembic."""
    _, source_url = scratch_db()
    _seed_source_db(source_url, turnos=3)
    origen_turnos, origen_rev = _counts(source_url)
    assert origen_turnos == 3

    backup_dir = tmp_path / "backups"
    dump_result = _run_backup(backup_dir, database_url=source_url)
    assert dump_result.returncode == 0, dump_result.stderr
    dump = next(backup_dir.glob("turnos_*.dump"))

    _, target_url = scratch_db()
    restore = _run_restore(dump, target_url, expected_turnos=3)

    assert restore.returncode == 0, restore.stderr
    destino_turnos, destino_rev = _counts(target_url)
    assert destino_turnos == origen_turnos
    assert destino_rev == origen_rev == "002_agenda_meta"


def test_restore_rechaza_target_no_vacio_sin_force(pg_test_url, tmp_path, scratch_db):
    """# AC DO-R3 ERROR — target con tablas exige `--force` explícito."""
    backup_dir = tmp_path / "backups"
    dump_result = _run_backup(backup_dir, database_url=pg_test_url)
    assert dump_result.returncode == 0, dump_result.stderr
    dump = next(backup_dir.glob("turnos_*.dump"))

    _, target_url = scratch_db()
    _alembic_upgrade(target_url)

    rechazo = _run_restore(dump, target_url)
    assert rechazo.returncode != 0
    assert "force" in (rechazo.stdout + rechazo.stderr).lower()

    forzado = _run_restore(dump, target_url, force=True)
    assert forzado.returncode == 0, forzado.stderr
    origen = _counts(pg_test_url)
    assert _counts(target_url) == origen


# --- Retry del teardown de bases scratch (DO-R3, regresión de flake) --------
#
# `DROP DATABASE ... WITH (FORCE)` puede fallar con 42501 si un autovacuum
# worker (superusuario) corre sobre la base: el rol de la app no puede
# terminarlo. 55006 (object_in_use) es el otro transitorio esperable. Lo único
# que se sustituye es el borde de la conexión SQL (regla dura 9), no la lógica
# del helper: por eso `_admin_engine` y `time.sleep` se parchean en el módulo.

_MODULO = sys.modules[__name__]


class _OrigenError(Exception):
    """Origen DB-API falso que expone `sqlstate`, como las excepciones de psycopg."""


def _error_db(
    sqlstate: str,
    tipo: type[sqlalchemy.exc.DBAPIError] = sqlalchemy.exc.ProgrammingError,
) -> sqlalchemy.exc.DBAPIError:
    origen = _OrigenError("error simulado")
    origen.sqlstate = sqlstate
    return tipo("DROP DATABASE", {}, origen)


class _ConexionFalsa:
    def __init__(self, error: BaseException | None) -> None:
        self._error = error

    def __enter__(self) -> "_ConexionFalsa":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def execute(self, _sentencia: object) -> None:
        if self._error is not None:
            raise self._error


class _MotorFalso:
    """Motor con guion: un error (o None) por cada intento de conexión."""

    def __init__(self, guion: list[BaseException | None]) -> None:
        self.guion = list(guion)
        self.intentos = 0
        self.desechado = False

    def connect(self) -> _ConexionFalsa:
        self.intentos += 1
        error = self.guion.pop(0) if self.guion else None
        return _ConexionFalsa(error)

    def dispose(self) -> None:
        self.desechado = True


class _TiempoFalso:
    def __init__(self, esperas: list[float]) -> None:
        self.esperas = esperas

    def sleep(self, segundos: float) -> None:
        self.esperas.append(segundos)


def _preparar_drop(
    monkeypatch: pytest.MonkeyPatch,
    guion: list[BaseException | None],
) -> tuple[_MotorFalso, list[float]]:
    motor = _MotorFalso(guion)
    esperas: list[float] = []
    monkeypatch.setattr(_MODULO, "_admin_engine", lambda: motor)
    monkeypatch.setattr(_MODULO, "time", _TiempoFalso(esperas))
    return motor, esperas


def test_drop_scratch_db_reintenta_42501_y_termina(monkeypatch):
    motor, esperas = _preparar_drop(monkeypatch, [_error_db("42501"), None])

    _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 2
    assert esperas == [0.2]
    assert motor.desechado is True


def test_drop_scratch_db_reintenta_55006_y_termina(monkeypatch):
    motor, esperas = _preparar_drop(
        monkeypatch, [_error_db("55006"), _error_db("42501"), None]
    )

    _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 3
    assert esperas == [0.2, 0.2]


def test_drop_scratch_db_no_reintenta_sqlstate_no_transitorio(monkeypatch):
    motor, esperas = _preparar_drop(monkeypatch, [_error_db("42P01")] * 10)

    with pytest.raises(sqlalchemy.exc.ProgrammingError):
        _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 1
    assert esperas == []


def test_drop_scratch_db_no_reintenta_error_no_dbapi(monkeypatch):
    motor, esperas = _preparar_drop(
        monkeypatch, [RuntimeError("fallo inesperado")] * 10
    )

    with pytest.raises(RuntimeError):
        _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 1
    assert esperas == []


def test_drop_scratch_db_agota_reintentos_y_relanza(monkeypatch):
    motor, esperas = _preparar_drop(monkeypatch, [_error_db("42501")] * 10)

    with pytest.raises(sqlalchemy.exc.ProgrammingError):
        _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 10
    assert esperas == [0.2] * 9


def test_drop_scratch_db_primer_intento_no_espera(monkeypatch):
    motor, esperas = _preparar_drop(monkeypatch, [None])

    _drop_scratch_db("turnos_bk_falso")

    assert motor.intentos == 1
    assert esperas == []

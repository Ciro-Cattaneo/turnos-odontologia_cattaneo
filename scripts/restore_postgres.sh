#!/usr/bin/env bash
# Restore de un dump generado por `scripts/backup_postgres.sh` (DO-R3, C-12 D-8).
#
# Contrato:
#   - Rechaza un target con tablas en `public` salvo `--force` explícito.
#   - Restaura con `pg_restore --clean --if-exists --no-owner --no-acl`.
#   - Verifica conteos post-restore y, si `EXPECTED_TURNO_COUNT` está definido,
#     falla cuando no coincide.
#   - Credenciales SOLO por la URL objetivo (se convierten a variables libpq),
#     nunca se imprimen ni se pasan por argumento visible más allá de la URL.
#
# Uso:
#   scripts/restore_postgres.sh <dump> <target-database-url> [--force]
#
# Ejemplo (datos ficticios, regla dura 12):
#   scripts/restore_postgres.sh backups/turnos_20261116T031700Z.dump \
#     "postgresql://turnos:changeme@localhost:5432/turnos_scratch" --force
#
# ADVERTENCIA: apuntá a una base scratch. Con `--force` se destruyen las
# tablas existentes del target.

set -euo pipefail

log() { printf '%s\n' "$*"; }
die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

dump=""
target=""
force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -*) die "opción desconocida: $arg" ;;
    *)
      if [ -z "$dump" ]; then
        dump="$arg"
      elif [ -z "$target" ]; then
        target="$arg"
      else
        die "argumentos de más: $arg"
      fi
      ;;
  esac
done

[ -n "$dump" ] || die "uso: $0 <dump> <target-database-url> [--force]"
[ -n "$target" ] || die "uso: $0 <dump> <target-database-url> [--force]"
[ -f "$dump" ] || die "no existe el dump: $dump"
command -v pg_restore >/dev/null 2>&1 || die "pg_restore no está en PATH"
command -v psql >/dev/null 2>&1 || die "psql no está en PATH (se usa para validar el target)"

url="${target%%\?*}"
rest="${url#*://}"
[ "$rest" != "$url" ] || die "URL objetivo inválida: falta el scheme 'postgresql://'"
if [[ "$rest" == *"@"* ]]; then
  creds="${rest%%@*}"
  rest="${rest#*@}"
  if [[ "$creds" == *":"* ]]; then
    PGUSER="${creds%%:*}"
    PGPASSWORD="${creds#*:}"
  else
    PGUSER="$creds"
  fi
fi
hostpart="${rest%%/*}"
PGDATABASE="${rest#*/}"
[ "$PGDATABASE" != "$rest" ] || die "URL objetivo inválida: falta el nombre de la base"
if [[ "$hostpart" == *":"* ]]; then
  PGHOST="${hostpart%%:*}"
  PGPORT="${hostpart##*:}"
else
  PGHOST="$hostpart"
  PGPORT=5432
fi
[ -n "$PGHOST" ] || die "URL objetivo inválida: falta el host"
[ -n "$PGDATABASE" ] || die "URL objetivo inválida: falta el nombre de la base"
export PGHOST PGPORT PGDATABASE
if [ -n "${PGUSER:-}" ]; then export PGUSER; fi
if [ -n "${PGPASSWORD:-}" ]; then export PGPASSWORD; fi

tablas="$(psql -tA -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'" \
  2>/dev/null)" || die "no se pudo conectar al target (revisá la URL y los permisos)"
tablas="${tablas//[[:space:]]/}"
if [ "${tablas:-0}" -gt 0 ] && [ "$force" -ne 1 ]; then
  die "el target no está vacío (${tablas} tablas en public); usá --force para sobrescribir"
fi

if ! pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error \
  --dbname="$PGDATABASE" "$dump"; then
  die "pg_restore falló"
fi

turnos="$(psql -tA -c 'SELECT count(*) FROM turno' 2>/dev/null || printf '0')"
turnos="${turnos//[[:space:]]/}"
revision="$(psql -tA -c 'SELECT version_num FROM alembic_version LIMIT 1' 2>/dev/null || printf '')"
revision="${revision//[[:space:]]/}"
log "restore ok: turno=${turnos} alembic=${revision:-<sin revisión>}"

if [ -n "${EXPECTED_TURNO_COUNT:-}" ]; then
  if [ "$turnos" != "$EXPECTED_TURNO_COUNT" ]; then
    die "conteo de turnos restaurado ($turnos) != esperado ($EXPECTED_TURNO_COUNT)"
  fi
fi

exit 0

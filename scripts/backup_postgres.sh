#!/usr/bin/env bash
# Backup diario de Postgres en formato custom (DO-R3, PB-05, C-12 D-8).
#
# Contrato:
#   - Escribe `turnos_<timestamp UTC>.dump` con `pg_dump -Fc`.
#   - Archivo temporal + rename atómico: sólo publica el dump si pasa
#     `pg_restore --list`, con permisos 600 (`umask 077` + `chmod 600`).
#   - Rota dumps con más de `BACKUP_RETENTION_DAYS` días (default 7).
#   - Credenciales SOLO por env (`DATABASE_URL` o variables libpq `PG*`),
#     nunca por argumento: la password jamás aparece en `ps` ni en logs.
#   - Exit != 0 ante cualquier fallo y sin dejar dump parcial.
#
# Uso:
#   scripts/backup_postgres.sh
#
# Variables:
#   BACKUP_DIR              destino (default: <repo>/backups)
#   BACKUP_RETENTION_DAYS   días a conservar (default: 7)
#   BACKUP_MODE             `direct` (default, cliente local) | `compose`
#   DATABASE_URL            URL de conexión (SQLAlchemy o libpq)
#   PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE  alternativa libpq
#
# Ejemplos (datos ficticios, regla dura 12):
#   DATABASE_URL="postgresql://turnos:changeme@localhost:5432/turnos" \
#     scripts/backup_postgres.sh
#   BACKUP_MODE=compose scripts/backup_postgres.sh   # usa el servicio `db`

set -euo pipefail
umask 077

BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
BACKUP_MODE="${BACKUP_MODE:-direct}"

log() { printf '%s\n' "$*"; }
die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

case "$BACKUP_MODE" in
  direct | compose) ;;
  *) die "BACKUP_MODE inválido: '$BACKUP_MODE' (usá 'direct' o 'compose')" ;;
esac

if ! [[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  die "BACKUP_RETENTION_DAYS debe ser un entero >= 1"
fi
if [ "$BACKUP_RETENTION_DAYS" -eq 0 ]; then
  die "BACKUP_RETENTION_DAYS debe ser >= 1 (no se permite retención 0)"
fi

_output_a_env() {
  # A partir de una URL `scheme://user:pass@host:port/db[?params]` exporta
  # las variables libpq. No imprime la URL: nunca filtra credenciales.
  local url="${1%%\?*}"
  local rest="${url#*://}"
  [ "$rest" != "$url" ] || die "URL de base inválida: falta el scheme 'postgresql://'"
  if [[ "$rest" == *"@"* ]]; then
    local creds="${rest%%@*}"
    rest="${rest#*@}"
    if [[ "$creds" == *":"* ]]; then
      PGUSER="${creds%%:*}"
      PGPASSWORD="${creds#*:}"
    else
      PGUSER="$creds"
    fi
  fi
  local hostpart="${rest%%/*}"
  local dbname="${rest#*/}"
  [ "$dbname" != "$rest" ] || die "URL de base inválida: falta el nombre de la base"
  dbname="${dbname:-}"
  if [[ "$hostpart" == *":"* ]]; then
    PGHOST="${hostpart%%:*}"
    PGPORT="${hostpart##*:}"
  else
    PGHOST="$hostpart"
    PGPORT=5432
  fi
  PGDATABASE="$dbname"
  [ -n "$PGHOST" ] || die "URL de base inválida: falta el host"
  [ -n "$PGDATABASE" ] || die "URL de base inválida: falta el nombre de la base"
  export PGHOST PGPORT PGDATABASE
  if [ -n "${PGUSER:-}" ]; then export PGUSER; fi
  if [ -n "${PGPASSWORD:-}" ]; then export PGPASSWORD; fi
}

if [ -n "${PGHOST:-}" ]; then
  PGPORT="${PGPORT:-5432}"
  [ -n "${PGDATABASE:-}" ] || die "falta PGDATABASE (o DATABASE_URL)"
  export PGPORT PGDATABASE
elif [ -n "${DATABASE_URL:-}" ]; then
  _output_a_env "$DATABASE_URL"
else
  die "faltan credenciales: definí DATABASE_URL o las variables libpq PG*"
fi

if [ "$BACKUP_MODE" = "direct" ]; then
  command -v pg_dump >/dev/null 2>&1 || die "pg_dump no está en PATH (cliente PostgreSQL)"
  command -v pg_restore >/dev/null 2>&1 || die "pg_restore no está en PATH (cliente PostgreSQL)"
else
  command -v docker >/dev/null 2>&1 || die "BACKUP_MODE=compose requiere docker en el host"
fi

mkdir -p "$BACKUP_DIR" || die "no se pudo crear BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
final="$BACKUP_DIR/turnos_${stamp}.dump"
n=1
while [ -e "$final" ]; do
  final="$BACKUP_DIR/turnos_${stamp}_${n}.dump"
  n=$((n + 1))
done
tmp="$BACKUP_DIR/.turnos_${stamp}.$$.dump.tmp"

tmp_vivo=0
cleanup() {
  if [ "$tmp_vivo" -eq 1 ] && [ -e "$tmp" ]; then
    rm -f -- "$tmp"
  fi
}
trap cleanup EXIT

tmp_vivo=1
if [ "$BACKUP_MODE" = "direct" ]; then
  if ! pg_dump -Fc --no-owner --no-acl -f "$tmp"; then
    die "pg_dump falló; no se generó ningún backup"
  fi
else
  if ! docker compose exec -T db pg_dump -Fc --no-owner --no-acl \
    -U "${PGUSER:-postgres}" "${PGDATABASE:-turnos}" >"$tmp"; then
    die "pg_dump (compose) falló; no se generó ningún backup"
  fi
fi

if command -v pg_restore >/dev/null 2>&1; then
  if ! pg_restore --list "$tmp" >/dev/null 2>&1; then
    die "el dump no pasó la verificación (pg_restore --list)"
  fi
else
  log "aviso: pg_restore no está en PATH; se omite la verificación del dump"
fi

chmod 600 "$tmp" || die "no se pudo aplicar el permiso 600 al dump"
if ! mv -f -- "$tmp" "$final"; then
  die "no se pudo publicar el dump (rename atómico)"
fi
tmp_vivo=0

bytes="$(wc -c <"$final" | tr -d '[:space:]')"
log "backup ok: $(basename "$final") (${bytes} bytes)"

while IFS= read -r viejo; do
  [ -n "$viejo" ] || continue
  rm -f -- "$viejo"
  log "rotado: $(basename "$viejo")"
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'turnos_*.dump' \
  -mtime "+${BACKUP_RETENTION_DAYS}" 2>/dev/null)

exit 0

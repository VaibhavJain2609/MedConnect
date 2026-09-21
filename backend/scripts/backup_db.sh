#!/usr/bin/env bash
# backup_db.sh — pg_dump both MedConnect databases out of the compose stack.
#
# Produces PostgreSQL *custom-format* (-Fc) archives, one per database:
#
#   backups/medconnect_YYYYMMDD_HHMMSS.dump
#   backups/medconnect_medicines_YYYYMMDD_HHMMSS.dump
#
# Custom format is compressed and selectively restorable — restore with
# backend/scripts/restore_db.sh (always into a scratch database) or plain
# pg_restore. See docs/backup-restore.md for the full workflow, including
# the RDS production path (snapshot-based — these scripts are for the
# docker-compose world only).
#
# Usage:
#   backend/scripts/backup_db.sh [--out DIR] [--latest]
#   make backup                       # same thing via the Makefile
#   make backup ARGS="--latest"
#
# Options:
#   --out DIR    Backup directory (default: ./backups under the repo root)
#   --latest     Also refresh <db>_latest.dump symlinks to the new archives
#
# Requires the compose `postgres` service to be running (`make up`).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Compose v2 preferred; docker-compose v1 binary as fallback (mirrors Makefile).
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "error: neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
fi

# Pick up POSTGRES_USER from the repo .env the same way compose does.
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi
PGUSER="${POSTGRES_USER:-medconnect}"

# The two logical databases (postgres/init.sql). Keycloak lives in a schema
# of `medconnect`, so a dump of it covers Keycloak data too.
DATABASES=(medconnect medconnect_medicines)

OUT_DIR="$REPO_ROOT/backups"
LATEST=0

usage() {
    sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//; /^set -euo/d'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)
            OUT_DIR="$(cd "$2" 2>/dev/null && pwd || echo "$2")"
            shift 2
            ;;
        --out=*)
            OUT_DIR="${1#*=}"
            shift
            ;;
        --latest)
            LATEST=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option '$1' (see --help)" >&2
            exit 2
            ;;
    esac
done

mkdir -p "$OUT_DIR"

if ! $COMPOSE ps postgres --status running --quiet 2>/dev/null | grep -q .; then
    echo "error: compose service 'postgres' is not running — start the stack with 'make up'" >&2
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
rc=0

for db in "${DATABASES[@]}"; do
    dest="$OUT_DIR/${db}_${STAMP}.dump"
    echo ">> dumping $db -> $dest"
    # Stream the archive out over stdout (exec -T) — nothing is written
    # inside the container, so no volume mounts or container cleanup needed.
    if $COMPOSE exec -T postgres pg_dump -Fc -U "$PGUSER" "$db" > "$dest"; then
        size=$(du -h "$dest" | cut -f1)
        if [[ ! -s "$dest" ]]; then
            echo "!! $db: dump is empty — removing" >&2
            rm -f "$dest"
            rc=1
            continue
        fi
        echo "   ok ($size)"
        if [[ "$LATEST" -eq 1 ]]; then
            ln -sfn "$(basename "$dest")" "$OUT_DIR/${db}_latest.dump"
        fi
    else
        echo "!! $db: pg_dump failed" >&2
        rm -f "$dest"
        rc=1
    fi
done

if [[ "$rc" -eq 0 ]]; then
    echo "backup complete -> $OUT_DIR"
else
    echo "backup finished WITH ERRORS — see above" >&2
fi
exit "$rc"

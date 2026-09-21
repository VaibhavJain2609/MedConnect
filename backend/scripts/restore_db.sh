#!/usr/bin/env bash
# restore_db.sh — restore a pg_dump custom-format archive into a SCRATCH
# database inside the compose postgres container.
#
# This is the restore half of the backup/restore drill (see
# docs/backup-restore.md). It is deliberately safe-by-default:
#
#   * The target database is REQUIRED via --db and must not already exist
#     (unless --recreate).
#   * The live database names (medconnect, medconnect_medicines) and system
#     databases are refused unless --i-know-what-im-doing is passed.
#   * Nothing is ever restored over the top of existing data silently.
#
# Usage:
#   backend/scripts/restore_db.sh --db drill_medconnect \
#       --file backups/medconnect_20250101_120000.dump [--recreate] [--cleanup]
#
# Options:
#   --db NAME                 Target (scratch) database name. Required.
#   --file PATH               .dump archive produced by backup_db.sh. Required.
#   --recreate                Drop the target database first if it exists.
#   --cleanup                 Drop the target database again after the
#                             post-restore sanity report (used by
#                             `make restore-drill`).
#   --i-know-what-im-doing    Allow restoring over a live database name.
#                             Never needed for drills; exists for real
#                             recovery only.
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

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi
PGUSER="${POSTGRES_USER:-medconnect}"

TARGET_DB=""
DUMP_FILE=""
RECREATE=0
CLEANUP=0
I_KNOW=0

# Names that must never be silently overwritten by this script.
PROTECTED_DBS=(medconnect medconnect_medicines postgres template0 template1)

usage() {
    sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//; /^set -euo/d'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db)
            TARGET_DB="$2"; shift 2 ;;
        --db=*)
            TARGET_DB="${1#*=}"; shift ;;
        --file)
            DUMP_FILE="$2"; shift 2 ;;
        --file=*)
            DUMP_FILE="${1#*=}"; shift ;;
        --recreate)
            RECREATE=1; shift ;;
        --cleanup)
            CLEANUP=1; shift ;;
        --i-know-what-im-doing)
            I_KNOW=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "error: unknown option '$1' (see --help)" >&2
            exit 2 ;;
    esac
done

if [[ -z "$TARGET_DB" ]]; then
    echo "error: --db NAME is required (a scratch database, not the live one)" >&2
    exit 2
fi
if [[ -z "$DUMP_FILE" ]]; then
    echo "error: --file PATH is required (a .dump archive from backup_db.sh)" >&2
    exit 2
fi
if [[ ! -f "$DUMP_FILE" ]]; then
    echo "error: dump file not found: $DUMP_FILE" >&2
    exit 2
fi

# Identifier validation — the name is interpolated into SQL/psql commands.
if [[ ! "$TARGET_DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "error: invalid database name '$TARGET_DB' (letters, digits, _ only)" >&2
    exit 2
fi

for protected in "${PROTECTED_DBS[@]}"; do
    if [[ "$TARGET_DB" == "$protected" && "$I_KNOW" -ne 1 ]]; then
        echo "error: refusing to restore over '$TARGET_DB'." >&2
        echo "       Restore into a scratch name (e.g. --db drill_${protected})." >&2
        echo "       For a real recovery, pass --i-know-what-im-doing explicitly." >&2
        exit 1
    fi
done

if ! $COMPOSE ps postgres --status running --quiet 2>/dev/null | grep -q .; then
    echo "error: compose service 'postgres' is not running — start the stack with 'make up'" >&2
    exit 1
fi

psql_admin() {
    $COMPOSE exec -T postgres psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 "$@"
}

db_exists() {
    [[ "$(psql_admin -Atc "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'")" == "1" ]]
}

if db_exists; then
    if [[ "$RECREATE" -eq 1 ]]; then
        echo ">> dropping existing database '$TARGET_DB' (--recreate)"
        $COMPOSE exec -T postgres dropdb -U "$PGUSER" --if-exists --force "$TARGET_DB"
    else
        echo "error: database '$TARGET_DB' already exists — pass --recreate to drop it first" >&2
        exit 1
    fi
fi

echo ">> creating scratch database '$TARGET_DB'"
psql_admin -c "CREATE DATABASE $TARGET_DB"

echo ">> restoring $DUMP_FILE -> $TARGET_DB"
restore_rc=0
# Custom-format archives are seekable, but streaming via stdin keeps the
# dump on the host — no file is copied into the container.
if ! cat "$DUMP_FILE" | $COMPOSE exec -T postgres \
        pg_restore -U "$PGUSER" --no-owner --no-privileges -d "$TARGET_DB"; then
    restore_rc=1
    echo "!! pg_restore reported errors — inspect the output above before trusting this restore" >&2
fi

echo ">> sanity check: row counts per public table"
# Dynamic count(*) per table — pg_stat_user_tables counters are unreliable
# immediately after a restore (stats haven't run yet).
psql_admin -d "$TARGET_DB" -At <<'SQL' | while IFS='|' read -r schema tbl; do
SELECT schemaname || '|' || tablename
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename;
SQL
    count="$($COMPOSE exec -T postgres psql -U "$PGUSER" -d "$TARGET_DB" -Atc \
        "SELECT count(*) FROM \"$schema\".\"$tbl\"" 2>/dev/null || echo '?')"
    printf '   %-40s %s\n' "$schema.$tbl" "$count"
done

if [[ "$CLEANUP" -eq 1 ]]; then
    echo ">> dropping scratch database '$TARGET_DB' (--cleanup)"
    $COMPOSE exec -T postgres dropdb -U "$PGUSER" --if-exists --force "$TARGET_DB"
    echo "restore drill complete: $TARGET_DB verified and cleaned up"
else
    echo "restore complete: '$TARGET_DB' left in place for inspection"
    echo "  drop it with: $COMPOSE exec postgres dropdb -U $PGUSER $TARGET_DB"
fi

exit "$restore_rc"

#!/usr/bin/env bash
#
# keycloak_erasure.sh — close the identity-provider gap in the DPDP erasure flow.
#
# POST /api/v1/patients/erasure anonymizes the application database but cannot
# touch Keycloak (the app holds no admin credential by design). The patient's
# email/name therefore persist in the IdP until an operator runs this script.
# See docs/dpdp-erasure.md for the full runbook.
#
# Two modes:
#
#   anonymize (default) — disable the Keycloak user and overwrite its PII
#     attributes (email/username/firstName/lastName) with tombstone values.
#     The Keycloak user id (= the `sub` claim = users.keycloak_sub in the app
#     DB) is kept, so the app-side keycloak_sub row still resolves and audit
#     trails stay anchored. If the same human re-registers they get a NEW sub
#     and a fresh app user — the tombstone keeps the old sub occupied so there
#     is never a collision. Requires PUT on the user.
#
#   delete — DELETE the Keycloak user outright. Frees the sub and removes the
#     IdP record entirely (strongest interpretation of erasure), but the app
#     DB keeps a users.keycloak_sub pointing at a now-nonexistent IdP id —
#     fine for FK integrity (the column is just a string) yet it means nothing
#     in Keycloak remains to corroborate the erasure audit trail. Choose this
#     only when policy demands full IdP removal.
#
# Usage:
#   keycloak_erasure.sh --sub <keycloak-user-id>   [--mode anonymize|delete] [--dry-run]
#   keycloak_erasure.sh --email <user@example.com> [--mode anonymize|delete] [--dry-run]
#
# Environment:
#   KEYCLOAK_URL             base URL (default http://localhost:8080)
#   KEYCLOAK_REALM           realm holding the user (default medconnect)
#   KEYCLOAK_ADMIN_USER      master-realm admin username (prompted if unset)
#   KEYCLOAK_ADMIN_PASSWORD  master-realm admin password (prompted, silent)
#
# Auth mirrors backend/app/utils/keycloak_admin.py: a password grant against
# the master realm's built-in `admin-cli` client. Until the backend migrates
# to the dedicated service-account client (tracked follow-up, see
# keycloak/realm-export.json), this script uses the same grant.

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-medconnect}"
MODE="anonymize"
DRY_RUN=0
LOOKUP_SUB=""
LOOKUP_EMAIL=""

ERASED_DOMAIN="erased.invalid"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*" >&2; }

usage() {
    sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --sub)     LOOKUP_SUB="${2:?--sub needs a value}"; shift 2 ;;
        --email)   LOOKUP_EMAIL="${2:?--email needs a value}"; shift 2 ;;
        --mode)    MODE="${2:?--mode needs a value}"; shift 2 ;;
        --realm)   REALM="${2:?--realm needs a value}"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage 0 ;;
        *) die "unknown argument: $1 (try --help)" ;;
    esac
done

[ "$MODE" = "anonymize" ] || [ "$MODE" = "delete" ] \
    || die "--mode must be 'anonymize' or 'delete'"
[ -n "$LOOKUP_SUB" ] || [ -n "$LOOKUP_EMAIL" ] \
    || die "one of --sub or --email is required"
{ [ -z "$LOOKUP_SUB" ] || [ -z "$LOOKUP_EMAIL" ]; } \
    || die "--sub and --email are mutually exclusive"

command -v curl >/dev/null || die "curl is required"

# Extract a value from a JSON document on stdin. jq if present, python3
# otherwise (both are safe to assume on an ops workstation).
#   $1 = jq -r expression        e.g. '.access_token' or '.[0].id // empty'
#   $2 = python expression on `d` (the parsed doc), e.g. "d['access_token']"
json_field() {
    if command -v jq >/dev/null; then
        jq -r "$1"
    else
        command -v python3 >/dev/null || die "need jq or python3 to parse Keycloak JSON"
        python3 -c "
import sys, json
d = json.load(sys.stdin)
r = ($2)
print(json.dumps(r) if isinstance(r, (dict, list)) else ('' if r is None else r))
"
    fi
}

# --- credentials ------------------------------------------------------------

if [ "$DRY_RUN" -eq 1 ]; then
    ADMIN_USER="${KEYCLOAK_ADMIN_USER:-<admin-user>}"
    ADMIN_PASS="<redacted>"
else
    ADMIN_USER="${KEYCLOAK_ADMIN_USER:-}"
    ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-}"
    if [ -z "$ADMIN_USER" ]; then
        printf 'Keycloak admin user: ' >&2
        read -r ADMIN_USER
    fi
    if [ -z "$ADMIN_PASS" ]; then
        printf 'Keycloak admin password: ' >&2
        read -rs ADMIN_PASS
        printf '\n' >&2
    fi
fi

# --- admin token (master realm, admin-cli — same grant as keycloak_admin.py) -

TOKEN_URL="$KEYCLOAK_URL/realms/master/protocol/openid-connect/token"
log "==> POST $TOKEN_URL (grant_type=password, client_id=admin-cli, user=$ADMIN_USER)"

if [ "$DRY_RUN" -eq 1 ]; then
    TOKEN="DRYRUN_TOKEN"
else
    token_resp="$(curl -fsS -X POST "$TOKEN_URL" \
        -d grant_type=password -d client_id=admin-cli \
        --data-urlencode "username=$ADMIN_USER" \
        --data-urlencode "password=$ADMIN_PASS")" \
        || die "admin token request failed (check KEYCLOAK_URL / credentials)"
    TOKEN="$(printf '%s' "$token_resp" | json_field '.access_token' "d['access_token']")"
    [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ] || die "no access_token in token response"
fi

AUTH="Authorization: Bearer $TOKEN"

# --- locate the user ----------------------------------------------------------

if [ -n "$LOOKUP_SUB" ]; then
    # The JWT `sub` claim is the Keycloak user UUID — direct lookup.
    USER_URL="$KEYCLOAK_URL/admin/realms/$REALM/users/$LOOKUP_SUB"
    log "==> GET $USER_URL"
    if [ "$DRY_RUN" -eq 1 ]; then
        KC_USER_ID="$LOOKUP_SUB"
        USER_JSON='{"id":"<dry-run>","username":"<dry-run>"}'
    else
        USER_JSON="$(curl -fsS -H "$AUTH" "$USER_URL")" \
            || die "no Keycloak user with id '$LOOKUP_SUB' in realm '$REALM' (try --email)"
        KC_USER_ID="$LOOKUP_SUB"
    fi
else
    SEARCH_URL="$KEYCLOAK_URL/admin/realms/$REALM/users?email=$LOOKUP_EMAIL&exact=true"
    log "==> GET $SEARCH_URL"
    if [ "$DRY_RUN" -eq 1 ]; then
        KC_USER_ID="<resolved-user-id>"
        USER_JSON='{"id":"<dry-run>","username":"<dry-run>"}'
    else
        matches="$(curl -fsS -H "$AUTH" "$SEARCH_URL")" \
            || die "user search failed"
        KC_USER_ID="$(printf '%s' "$matches" \
            | json_field '.[0].id // empty' "d[0]['id'] if d else ''")"
        [ -n "$KC_USER_ID" ] \
            || die "no Keycloak user with email '$LOOKUP_EMAIL' in realm '$REALM'"
        USER_JSON="$(printf '%s' "$matches" \
            | json_field '.[0] // {}' "d[0] if d else {}")"
    fi
fi

log "    keycloak user id: $KC_USER_ID"

# --- act ----------------------------------------------------------------------

if [ "$MODE" = "delete" ]; then
    log "==> POST $KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID/logout"
    log "==> DELETE $KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID"
    if [ "$DRY_RUN" -eq 0 ]; then
        # Kill live sessions first so a racing refresh token can't outlive us.
        curl -fsS -X POST -H "$AUTH" \
            "$KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID/logout" || true
        curl -fsS -X DELETE -H "$AUTH" \
            "$KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID" \
            || die "DELETE failed"
    fi
    log "done: keycloak user $KC_USER_ID deleted from realm '$REALM'"
else
    TOMBSTONE_EMAIL="erased-$KC_USER_ID@$ERASED_DOMAIN"
    ERASED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    log "==> POST $KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID/logout"
    log "==> PUT  $KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID"
    log "    body: enabled=false, email=username=$TOMBSTONE_EMAIL, firstName=Erased, lastName=User, attributes={erased,erased_at}"

    if [ "$DRY_RUN" -eq 0 ]; then
        curl -fsS -X POST -H "$AUTH" \
            "$KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID/logout" || true

        # Build the PUT body from the fetched representation: overwrite the PII
        # fields and REPLACE attributes wholesale — user attributes may carry
        # PII (e.g. phone) and erasure should not preserve them. username must
        # follow email because the realm sets registrationEmailAsUsername.
        body="$(printf '%s' "$USER_JSON" \
            | TOMBSTONE_EMAIL="$TOMBSTONE_EMAIL" ERASED_AT="$ERASED_AT" python3 -c '
import json, os, sys
rep = json.load(sys.stdin)
rep.update({
    "enabled": False,
    "email": os.environ["TOMBSTONE_EMAIL"],
    "username": os.environ["TOMBSTONE_EMAIL"],
    "firstName": "Erased",
    "lastName": "User",
    "emailVerified": False,
    "requiredActions": [],
    "attributes": {"erased": ["true"], "erased_at": [os.environ["ERASED_AT"]]},
})
json.dump(rep, sys.stdout)
')" || die "failed to build anonymized user representation (python3 required)"

        curl -fsS -X PUT -H "$AUTH" -H 'Content-Type: application/json' \
            -d "$body" \
            "$KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID" \
            || die "PUT (anonymize) failed"

        # Verify: refetch and confirm the tombstone landed.
        after="$(curl -fsS -H "$AUTH" \
            "$KEYCLOAK_URL/admin/realms/$REALM/users/$KC_USER_ID")"
        enabled="$(printf '%s' "$after" | json_field '.enabled' "d['enabled']")"
        email="$(printf '%s' "$after" | json_field '.email' "d['email']")"
        log "    verify: enabled=$enabled email=$email"
        [ "$enabled" = "false" ] || [ "$enabled" = "False" ] \
            || die "verification failed: user still enabled"
        [ "$email" = "$TOMBSTONE_EMAIL" ] \
            || die "verification failed: email not tombstoned"
    fi
    log "done: keycloak user $KC_USER_ID anonymized + disabled (sub retained)"
fi

[ "$DRY_RUN" -eq 1 ] && log "(dry-run: no calls were made)"
exit 0

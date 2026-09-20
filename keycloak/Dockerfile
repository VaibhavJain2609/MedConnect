# Pinned to a specific patch release — the previous tag (24.0) is EOL.
# Latest 26.x at time of pinning; bump deliberately after reviewing
# https://www.keycloak.org/docs/latest/release_notes/
FROM quay.io/keycloak/keycloak:26.7.4

# NOTE: the realm-export.json baked into the image here is the docker-compose
# local-dev realm (compose runs `command: start-dev`; permissive settings —
# sslRequired=none, open registration — are intentional for localhost). In k8s
# this file is never used: infra/k8s/base/keycloak/deployment.yaml runs
# `start --optimized` (NOT start-dev — confirmed) and mounts the hardened
# per-environment realm ConfigMap over /opt/keycloak/data/import, shadowing
# this COPY.
# Known follow-up: backend/app/utils/keycloak_admin.py still authenticates to
# the master realm via the `admin-cli` password grant (KEYCLOAK_ADMIN_*). All
# realm exports now include a dedicated `medconnect-backend-admin`
# service-account client so the backend can migrate to client_credentials;
# the app-side change is tracked separately.
COPY realm-export.json /opt/keycloak/data/import/realm-export.json

# `kc.sh build` bakes these feature toggles and the DB driver choice into the
# image. docker-compose's `start-dev` doesn't need this (dev mode re-builds
# on every boot), but infra/k8s/base/keycloak/deployment.yaml runs
# `start --optimized` in production, which *requires* a prior build — without
# it the health endpoints my readiness/liveness probes hit
# (/health/ready, /health/live) would not exist.
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true
ENV KC_DB=postgres
RUN /opt/keycloak/bin/kc.sh build

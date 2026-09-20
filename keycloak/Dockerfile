FROM quay.io/keycloak/keycloak:24.0
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

"""Locust load tests for the MedConnect backend.

Quickstart (see loadtest/README.md for the full guide):

    pip install locust
    export LOCUST_TOKEN=<keycloak access token>
    locust -f loadtest/locustfile.py --host http://localhost:8000

Headless via Make:

    make loadtest TARGET=http://localhost:8000 USERS=50 RATE=5 TIME=5m
    make loadtest-smoke                      # no auth needed

User classes — pass one as a positional arg to run only that class:

    locust -f loadtest/locustfile.py --host http://localhost:8000 SmokeUser
    locust -f loadtest/locustfile.py --host http://localhost:8000 SoakUser

Optional spike profile: export LOCUST_SPIKE=1 to activate the SpikeShape
LoadTestShape defined below (it takes over user/spawn-rate control, so -u/-r
are ignored in that mode). Without the env var no shape is registered and the
usual -u/-r/-t behaviour applies.

NOTE: the backend rate-limits per caller (see app/middleware/rate_limit.py).
A single LOCUST_TOKEN shares one `token:<hash>` read bucket (~100 req/min),
so expect 429s above ~2 rps on authed endpoints — documented in the README.
"""

import os
import random

from locust import HttpUser, LoadTestShape, between, events, task
from locust.exception import StopUser

# Realistic-ish medicine search terms — repeated across users so the Redis
# `medcat:*` cache (medicine_cache.py) gets both hits and misses.
SEARCH_TERMS = [
    "para",
    "crocin",
    "dolo",
    "amox",
    "azithro",
    "ibu",
    "met",
    "ceti",
    "ome",
    "vita",
]


def _token() -> str:
    return os.environ.get("LOCUST_TOKEN", "")


@events.test_start.add_listener
def _warn_if_no_token(environment, **kwargs):
    if not _token():
        print(
            "\nloadtest: LOCUST_TOKEN is not set — MedConnectUser/SoakUser "
            "instances will stop immediately. Run the SmokeUser class for a "
            "no-auth run, or export a Keycloak access token "
            "(see loadtest/README.md).\n"
        )


class MedConnectUser(HttpUser):
    """Realistic portal traffic mix. Requires LOCUST_TOKEN (Keycloak JWT).

    Weighting reflects expected production traffic: medicine search is the
    hot path (front of the medcat Redis cache), notifications/appointments
    polls are moderate, and /health is a low-rate deep-check probe.
    """

    # Class weights: in a no-filter run Locust picks a class per spawn —
    # 60% authed portal mix, 20% anonymous smoke, 20% soak pace.
    weight = 3
    wait_time = between(0.5, 2)

    def on_start(self):
        token = _token()
        if not token:
            # Stop gracefully instead of generating a storm of 401s.
            raise StopUser()
        self.client.headers["Authorization"] = f"Bearer {token}"

    @task(6)
    def search_medicines(self):
        self.client.get(
            "/api/v1/medicines/search",
            params={"q": random.choice(SEARCH_TERMS), "limit": 20},
            name="/api/v1/medicines/search?q=<term>",
        )

    @task(3)
    def list_notifications(self):
        self.client.get(
            "/api/v1/notifications",
            params={"limit": 20},
            name="/api/v1/notifications",
        )

    @task(2)
    def list_appointments(self):
        self.client.get(
            "/api/v1/appointments",
            params={"limit": 20},
            name="/api/v1/appointments",
        )

    @task(1)
    def health(self):
        # Deep readiness: probes main DB + medicine DB + Redis.
        self.client.get("/health")


class SmokeUser(HttpUser):
    """No-auth smoke traffic: /health + /docs only.

    Both paths are exempt from rate limiting (_EXEMPT_PATHS), so this class
    can push real request volume without a token — good for a quick sanity
    check that the stack holds up.
    """

    weight = 1
    wait_time = between(0.5, 2)

    @task(3)
    def health(self):
        # 200 = db + medicine_db + redis all ok; 503 names the failing dep.
        self.client.get("/health")

    @task(1)
    def docs(self):
        self.client.get("/docs")


class SoakUser(MedConnectUser):
    """Same traffic mix as MedConnectUser at a relaxed pace.

    For long-duration runs (e.g. `-u 20 -r 1 -t 2h`) to surface leaks,
    connection-pool drift, and cache/memory growth rather than peak load.
    """

    weight = 1
    wait_time = between(2, 5)


# Defined only when opted in — a registered LoadTestShape takes over user
# count/spawn-rate control (and -u/-r are ignored), so we only create the
# class when LOCUST_SPIKE=1.
if os.environ.get("LOCUST_SPIKE") == "1":

    class SpikeShape(LoadTestShape):
        """Baseline → sharp ramp → sustained spike → drop (~3 min total).

        tick() returning None at the end stops the test; combine with -t if
        you want a hard bound.
        """

        stages = [
            # (duration_s, users, spawn_rate) — cumulative durations
            {"duration": 30, "users": 10, "spawn_rate": 5},
            {"duration": 60, "users": 150, "spawn_rate": 25},  # 30s ramp
            {"duration": 120, "users": 150, "spawn_rate": 25},  # hold
            {"duration": 150, "users": 10, "spawn_rate": 25},  # drop back
        ]

        def tick(self):
            run_time = self.get_run_time()
            for stage in self.stages:
                if run_time < stage["duration"]:
                    return stage["users"], stage["spawn_rate"]
            return None

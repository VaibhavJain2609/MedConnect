# Multi-stage build: `builder` compiles the Python venv with toolchain-only
# packages (gcc, libpq-dev); `runtime` ships just the venv + app code, so the
# signed image contains no compiler and no system build deps.
#
# Pinning policy: base images are pinned to a specific patch tag (never
# `latest` or bare major). Bump deliberately after reviewing changelogs.

FROM python:3.12.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc + libpq-dev are required only to build wheels at this stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12.12-slim AS runtime

WORKDIR /app

# curl is kept for the container HEALTHCHECK. psycopg2-binary and asyncpg
# ship their own libpq, so no system DB libraries are needed here.
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to JSON for frontend type generation.

Usage (from backend/):
    python scripts/export_openapi.py                  # -> ../frontend/openapi.json
    python scripts/export_openapi.py -o /tmp/spec.json

Safe to run without a database, Redis or Keycloak: ``app.openapi()`` builds the
schema purely from route/pydantic metadata — the app's lifespan (JWKS prewarm,
engine disposal) never runs because the ASGI app is never started. Engine
*objects* are constructed at import time but make no connections.
"""

import argparse
import json
import sys
from pathlib import Path

# Make `app` importable when run as `python scripts/export_openapi.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    # Import inside main so --help works without the full app import.
    from app.main import app

    spec = app.openapi()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + trailing newline keep the artifact diff-stable so CI and
    # humans can review contract changes cleanly.
    output.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")

    path_count = len(spec.get("paths", {}))
    schema_count = len(spec.get("components", {}).get("schemas", {}))
    print(f"Wrote {output} ({path_count} paths, {schema_count} schemas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

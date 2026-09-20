-- This script runs ONCE, on first boot of the postgres container, via
-- docker-entrypoint-initdb.d — i.e. only when the data volume is empty.
-- It is a dev/local convenience and never runs against production.

-- Keycloak stores its data in a dedicated schema of the main database
CREATE SCHEMA IF NOT EXISTS keycloak;

-- Application databases
CREATE DATABASE medconnect_medicines;

-- Test databases expected by the pytest suite (backend/tests/conftest.py:
-- medconnect_test on :5432, medicine_db_test on :5433). Created
-- unconditionally — this script only ever runs in the local dev container.
CREATE DATABASE medconnect_test;
CREATE DATABASE medicine_db_test;

-- Extensions required by the medicine catalog: pg_trgm for trigram/fuzzy
-- search and pgvector for embedding columns. Extensions are per-database,
-- so they must be created inside each database that uses them.
\connect medconnect_medicines
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Mirror the extensions in the medicine test DB so schema-creating fixtures
-- (Vector columns, trigram indexes) work identically in tests.
\connect medicine_db_test
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

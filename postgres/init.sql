-- Create keycloak schema for Keycloak to use
CREATE SCHEMA IF NOT EXISTS keycloak;

-- Create test database for pytest
CREATE DATABASE medconnect_test;

-- Create separate medicine database
CREATE DATABASE medconnect_medicines;

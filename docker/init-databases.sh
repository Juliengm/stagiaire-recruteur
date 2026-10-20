#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
  CREATE DATABASE veille;
  CREATE DATABASE dagster;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname veille -c "CREATE EXTENSION IF NOT EXISTS vector;"

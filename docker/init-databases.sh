#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
  CREATE DATABASE veille;
  CREATE DATABASE dagster;
  CREATE DATABASE veille_test;
SQL
for db in veille veille_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "CREATE EXTENSION IF NOT EXISTS vector;"
done

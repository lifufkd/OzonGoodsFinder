#!/bin/sh

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "$DB_HOST" -p 5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is ready."

echo "Running migrations..."
alembic upgrade head

#echo "Installing Playwright dependencies..."
#playwright install --with-deps

echo "Starting setup script..."
PYTHONPATH=. python src/main.py

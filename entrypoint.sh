#!/bin/sh

# 1. Wait for Postgres (Using Python instead of netcat)
echo "Waiting for postgres at $POSTGRES_HOST:$POSTGRES_PORT..."

# Loop until Python can connect to the DB port
while ! python -c "import socket; s = socket.socket(); s.connect(('$POSTGRES_HOST', int('$POSTGRES_PORT')))" 2>/dev/null; do
  sleep 1
done

echo "✅ PostgreSQL started"

# 2. Run Migrations (Only on the API container)
# We check if the command passed is 'uvicorn' (which is what the API runs)
if echo "$@" | grep -q "uvicorn"; then
    echo "Running Alembic Migrations..."
    alembic upgrade head
fi

# 3. Exec the passed command
exec "$@"
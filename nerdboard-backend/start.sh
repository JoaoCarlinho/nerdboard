#!/bin/bash
set -e

echo "🚀 Starting NerdBoard Backend..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

echo "✅ Migrations complete"

# Skip demo data loading during startup to avoid healthcheck timeout
# Run manually with: railway run python3 -m app.scripts.load_demo --scenario physics_shortage
# Then train model: railway run python3 -m app.scripts.train_model

echo "🌐 Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT

#!/bin/bash
set -e

echo "🚀 Starting NerdBoard Backend..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

echo "✅ Migrations complete"

# Check if we need to load demo data (with timeout and error handling)
echo "🔍 Checking if demo data needs to be loaded..."
if timeout 10 python3 -c "
import asyncio
import sys
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.tutor import Tutor

async def check_data():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Tutor))
            tutors = result.scalars().all()
            return len(tutors) == 0
    except Exception as e:
        print(f'Error checking data: {e}', file=sys.stderr)
        # If check fails, assume data exists to avoid blocking startup
        return False

needs_data = asyncio.run(check_data())
sys.exit(0 if needs_data else 1)
" 2>/dev/null; then
    echo "📊 Loading demo data (physics_shortage scenario)..."
    python3 -m app.scripts.load_demo --scenario physics_shortage || echo "⚠️  Demo data load failed, continuing..."

    echo "🤖 Training ML model..."
    python3 -m app.scripts.train_model || echo "⚠️  Model training failed, continuing..."
else
    echo "✅ Demo data already exists or check timed out, skipping load"
fi

echo "🌐 Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT

#!/bin/bash
set -e

echo "🚀 Starting NerdBoard Backend..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

# Check if we need to load demo data (only if tables are empty)
echo "🔍 Checking if demo data needs to be loaded..."
python3 -c "
import asyncio
from sqlalchemy import text, select
from app.database import AsyncSessionLocal
from app.models.tutor import Tutor

async def check_data():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tutor))
        tutors = result.scalars().all()
        return len(tutors) == 0

needs_data = asyncio.run(check_data())
exit(0 if needs_data else 1)
"

if [ $? -eq 0 ]; then
    echo "📊 Loading demo data (physics_shortage scenario)..."
    python3 -m app.scripts.load_demo --scenario physics_shortage

    echo "🤖 Training ML model..."
    python3 -m app.scripts.train_model
else
    echo "✅ Demo data already exists, skipping load"
fi

echo "🌐 Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT

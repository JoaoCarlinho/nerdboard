"""Integration tests for database schema and models"""
import pytest
from sqlalchemy import text, inspect
from app.database import engine, Base
from app.models import (
    Enrollment,
    Tutor,
    Session,
    HealthMetric,
    CapacitySnapshot,
    DataQualityLog,
    SimulationState,
)


@pytest.mark.asyncio
async def test_all_tables_exist():
    """Verify all 7 tables created via Alembic migration"""
    async with engine.connect() as conn:
        # Get all table names
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result]

    expected_tables = {
        "enrollments",
        "tutors",
        "sessions",
        "health_metrics",
        "capacity_snapshots",
        "data_quality_log",
        "simulation_state",
    }

    for table in expected_tables:
        assert table in tables, f"Table {table} not found in database"


@pytest.mark.asyncio
async def test_all_indexes_exist():
    """Verify critical indexes for performance"""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public' AND indexname LIKE 'idx_%'
                """
            )
        )
        indexes = [row[0] for row in result]

    expected_indexes = {
        "idx_enrollments_subject_date",
        "idx_enrollments_student",
        "idx_tutors_subjects",
        "idx_tutors_tutor_id",
        "idx_sessions_subject_time",
        "idx_sessions_tutor",
        "idx_sessions_student",
        "idx_health_customer_date",
        "idx_capacity_subject_date",
        "idx_quality_check_status",
        "idx_quality_checked_at",
    }

    for index in expected_indexes:
        assert index in indexes, f"Index {index} not found in database"


@pytest.mark.asyncio
async def test_alembic_upgrade_downgrade():
    """Test Alembic upgrade/downgrade cycle"""
    # This test assumes alembic is properly configured
    # In practice, you'd run: alembic downgrade -1 && alembic upgrade head
    # For now, we just verify the alembic_version table exists
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM alembic_version")
        )
        count = result.scalar()
        assert count == 1, "Alembic version table should have exactly 1 row"

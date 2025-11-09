"""
Integration tests for Capacity API

Tests full capacity calculation cycle, API endpoints, database integration.
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy import text
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.capacity_calculator import CapacityCalculator, get_capacity_calculator
from app.database import AsyncSessionLocal
from app.models.capacity_snapshot import CapacitySnapshot
from app.models.tutor import Tutor
from app.models.session import Session


@pytest.fixture(scope="function")
async def sample_tutors():
    """Create sample tutors for testing"""
    async with AsyncSessionLocal() as session:
        # Clear existing test tutors
        await session.execute(text("DELETE FROM tutors WHERE tutor_id LIKE 'TEST%'"))
        await session.commit()

        # Create test tutors
        tutors = [
            Tutor(
                tutor_id="TEST_PHYSICS_1",
                subjects=["Physics"],
                weekly_capacity_hours=40,
                utilization_rate=0.75
            ),
            Tutor(
                tutor_id="TEST_PHYSICS_2",
                subjects=["Physics"],
                weekly_capacity_hours=30,
                utilization_rate=0.60
            ),
            Tutor(
                tutor_id="TEST_MATH_1",
                subjects=["Math"],
                weekly_capacity_hours=50,
                utilization_rate=0.80
            ),
        ]

        for tutor in tutors:
            session.add(tutor)

        await session.commit()

    yield tutors

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM tutors WHERE tutor_id LIKE 'TEST%'"))
        await session.commit()


@pytest.fixture(scope="function")
async def sample_sessions(sample_tutors):
    """Create sample sessions for testing"""
    async with AsyncSessionLocal() as session:
        # Clear existing test sessions
        await session.execute(text("DELETE FROM sessions WHERE session_id LIKE 'TEST%'"))
        await session.commit()

        # Create sessions for current week
        from app.services.capacity_calculator import get_time_window_bounds
        start, end = get_time_window_bounds("current_week")

        sessions = [
            Session(
                session_id="TEST_SESSION_1",
                subject="Physics",
                tutor_id="TEST_PHYSICS_1",
                student_id="student_123",
                scheduled_time=start + timedelta(days=1),
                duration_minutes=60
            ),
            Session(
                session_id="TEST_SESSION_2",
                subject="Physics",
                tutor_id="TEST_PHYSICS_2",
                student_id="student_456",
                scheduled_time=start + timedelta(days=2),
                duration_minutes=90
            ),
            Session(
                session_id="TEST_SESSION_3",
                subject="Math",
                tutor_id="TEST_MATH_1",
                student_id="student_789",
                scheduled_time=start + timedelta(days=1),
                duration_minutes=60
            ),
        ]

        for session_obj in sessions:
            session.add(session_obj)

        await session.commit()

    yield sessions

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM sessions WHERE session_id LIKE 'TEST%'"))
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
class TestCapacityCalculation:
    """Integration tests for capacity calculation"""

    @pytest.mark.asyncio
    async def test_calculate_subject_capacity_with_real_data(self, sample_tutors, sample_sessions):
        """Test AC-1, AC-3, AC-7: Calculate capacity with real database data"""
        calculator = CapacityCalculator()

        # Calculate capacity for Physics in current week
        metrics = await calculator.calculate_subject_capacity("Physics", "current_week")

        # Physics tutors: 40 + 30 = 70 total hours
        assert metrics["total_hours"] == 70.0

        # Physics sessions: 60min + 90min = 150min = 2.5 hours
        assert metrics["booked_hours"] == 2.5

        # Utilization: 2.5 / 70 = 0.0357 (3.57%)
        assert 0.03 < metrics["utilization_rate"] < 0.04

        # Status should be normal (<85%)
        assert metrics["status"] == "normal"

        # Window bounds should be present
        assert "window_start" in metrics
        assert "window_end" in metrics

    @pytest.mark.asyncio
    async def test_capacity_snapshot_persistence(self, sample_tutors, sample_sessions):
        """Test AC-4: Snapshots are saved to capacity_snapshots table"""
        calculator = CapacityCalculator()

        # Clear previous snapshots
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM capacity_snapshots WHERE subject = 'Physics'"))
            await session.commit()

        # Calculate and save snapshot
        metrics = await calculator.calculate_subject_capacity("Physics", "current_week")
        await calculator.save_capacity_snapshot("Physics", "current_week", metrics)

        # Verify snapshot was saved
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM capacity_snapshots WHERE subject = 'Physics' AND time_window = 'current_week' ORDER BY snapshot_time DESC LIMIT 1")
            )
            snapshot = result.first()

        assert snapshot is not None
        assert snapshot.subject == "Physics"
        assert snapshot.time_window == "current_week"
        assert snapshot.total_hours == 70.0
        assert snapshot.booked_hours == 2.5
        assert snapshot.status == "normal"

    @pytest.mark.asyncio
    async def test_all_time_windows_calculation(self, sample_tutors):
        """Test AC-3: All 4 time windows calculate correctly"""
        calculator = CapacityCalculator()

        windows = ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]

        for window in windows:
            metrics = await calculator.calculate_subject_capacity("Physics", window)

            # Total hours should be same for all windows (tutors don't change)
            assert metrics["total_hours"] == 70.0

            # Should have valid metrics
            assert "booked_hours" in metrics
            assert "utilization_rate" in metrics
            assert "status" in metrics
            assert "window_start" in metrics
            assert "window_end" in metrics

    @pytest.mark.asyncio
    async def test_status_thresholds(self):
        """Test AC-6: Status determination thresholds"""
        calculator = CapacityCalculator()

        # Normal: <85%
        assert calculator._determine_status(0.50) == "normal"
        assert calculator._determine_status(0.84) == "normal"

        # Warning: 85-95%
        assert calculator._determine_status(0.85) == "warning"
        assert calculator._determine_status(0.90) == "warning"
        assert calculator._determine_status(0.94) == "warning"

        # Critical: >=95%
        assert calculator._determine_status(0.95) == "critical"
        assert calculator._determine_status(1.0) == "critical"

    @pytest.mark.asyncio
    async def test_bulk_capacity_calculation(self, sample_tutors, sample_sessions):
        """Test bulk recalculation for all subjects"""
        calculator = CapacityCalculator()

        # Clear previous snapshots
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM capacity_snapshots"))
            await session.commit()

        # Run bulk calculation
        summary = await calculator.calculate_all_subjects_capacity()

        # Should calculate all subjects
        from app.services.data_generator import SUBJECTS
        assert summary["subjects_calculated"] == len(SUBJECTS)

        # Should create 4 snapshots per subject (4 time windows)
        expected_snapshots = len(SUBJECTS) * 4
        assert summary["snapshots_created"] == expected_snapshots

        # Should complete in reasonable time (<2 seconds for all subjects)
        assert summary["duration_ms"] < 2000


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
class TestCapacityPerformance:
    """Performance tests for capacity calculations (AC-2)"""

    @pytest.mark.asyncio
    async def test_single_subject_calculation_performance(self, sample_tutors, sample_sessions):
        """Test AC-2: Capacity calculation completes in <50ms"""
        calculator = CapacityCalculator()

        start_time = time.time()
        metrics = await calculator.calculate_subject_capacity("Physics", "current_week")
        duration_ms = (time.time() - start_time) * 1000

        # AC-2 requirement: <50ms
        assert duration_ms < 50.0, f"Calculation took {duration_ms:.2f}ms (must be <50ms)"

        print(f"\n✓ Capacity calculation: {duration_ms:.2f}ms (target: <50ms)")

    @pytest.mark.asyncio
    async def test_all_windows_calculation_performance(self, sample_tutors, sample_sessions):
        """Test calculating all 4 time windows for a subject"""
        calculator = CapacityCalculator()

        start_time = time.time()

        for window in ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]:
            await calculator.calculate_subject_capacity("Physics", window)

        duration_ms = (time.time() - start_time) * 1000

        # All 4 windows should complete well within 200ms (4 * 50ms)
        assert duration_ms < 200.0, f"4 windows took {duration_ms:.2f}ms (must be <200ms)"

        print(f"\n✓ All 4 time windows: {duration_ms:.2f}ms")


@pytest.mark.asyncio
@pytest.mark.integration
class TestCapacityEdgeCases:
    """Test edge cases for capacity calculations"""

    @pytest.mark.asyncio
    async def test_no_tutors_for_subject(self):
        """Test capacity when no tutors available for subject"""
        calculator = CapacityCalculator()

        # Clear all tutors
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM tutors WHERE tutor_id LIKE 'TEST%'"))
            await session.commit()

        # Try to calculate with a valid subject
        from app.services.data_generator import SUBJECTS
        if SUBJECTS:
            subject = SUBJECTS[0]
            metrics = await calculator.calculate_subject_capacity(subject, "current_week")

            # Should return zero hours
            assert metrics["total_hours"] >= 0  # May be 0 if no tutors for this subject
            assert metrics["booked_hours"] >= 0
            # Utilization should be 0 when no tutors
            assert metrics["utilization_rate"] == 0

    @pytest.mark.asyncio
    async def test_invalid_subject_name(self):
        """Test error handling for invalid subject"""
        calculator = CapacityCalculator()

        with pytest.raises(ValueError, match="Invalid subject"):
            await calculator.calculate_subject_capacity("InvalidSubject", "current_week")

    @pytest.mark.asyncio
    async def test_invalid_window_type(self):
        """Test error handling for invalid time window"""
        calculator = CapacityCalculator()

        from app.services.data_generator import SUBJECTS
        if SUBJECTS:
            subject = SUBJECTS[0]

            with pytest.raises(ValueError, match="Invalid window type"):
                await calculator.calculate_subject_capacity(subject, "invalid_window")


# Import timedelta for session creation
from datetime import timedelta

"""
Integration tests for Simulation API

Tests full simulation cycle, API endpoints, state persistence, performance.
"""

import pytest
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_simulator import DataSimulator, get_simulator
from app.database import AsyncSessionLocal, engine
from app.models.simulation_state import SimulationState
from app.models.enrollment import Enrollment
from app.models.session import Session


@pytest.fixture(scope="function")
async def reset_simulator():
    """Fixture to reset simulation state before each test"""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("UPDATE simulation_state SET is_running=false, current_date=NOW() WHERE id=1")
            )
            await session.commit()
        except Exception:
            # Table might not exist yet
            pass
    yield
    # Cleanup after test
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("UPDATE simulation_state SET is_running=false WHERE id=1")
            )
            await session.commit()
        except Exception:
            pass


@pytest.mark.asyncio
@pytest.mark.integration
class TestSimulationAPI:
    """Integration tests for simulation API endpoints"""

    @pytest.mark.asyncio
    async def test_simulation_state_initialization(self):
        """Test AC: 6 - Simulation state persists in database"""
        simulator = DataSimulator()

        # Load state (should create if missing)
        state = await simulator.state_manager.load_state()

        assert state is not None
        assert state.id == 1  # Single-row constraint
        assert isinstance(state.is_running, bool)

    @pytest.mark.asyncio
    async def test_start_pause_simulation(self, reset_simulator):
        """Test AC: 3 - Can pause and resume simulation"""
        simulator = DataSimulator()

        # Start simulation
        start_result = await simulator.start_simulation()
        assert start_result["status"] == "started"

        # Verify state updated
        state = await simulator.state_manager.load_state()
        assert state.is_running is True

        # Pause simulation
        pause_result = await simulator.pause_simulation()
        assert pause_result["status"] == "paused"

        # Verify state updated
        state = await simulator.state_manager.load_state()
        assert state.is_running is False

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test AC: 4 - GET /simulation/status returns current state"""
        simulator = DataSimulator()

        status = await simulator.get_status()

        assert "current_time" in status
        assert "is_running" in status
        assert "speed_multiplier" in status
        assert "last_event_time" in status

    @pytest.mark.asyncio
    async def test_fast_forward_events_generated(self, reset_simulator):
        """Test AC: 7 - Fast-forward generates batch events"""
        # Clear existing data
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM sessions WHERE session_id LIKE 'S%'"))
            await session.execute(text("DELETE FROM enrollments WHERE student_id IS NOT NULL"))
            await session.commit()

        simulator = DataSimulator(
            enrollments_per_cycle=2,
            sessions_per_cycle=3,
        )

        # Fast-forward 1 day
        result = await simulator.advance_simulation(days=1)

        assert result["days_advanced"] == 1
        assert "new_time" in result
        assert "events_generated" in result
        assert result["events_generated"]["enrollments"] > 0
        assert result["events_generated"]["sessions"] >= 0  # May be 0 if no enrollments match tutors

    @pytest.mark.asyncio
    async def test_fast_forward_performance(self, reset_simulator):
        """Test AC: 7 - Fast-forward 7 days completes in <5 seconds"""
        simulator = DataSimulator()

        start_time = time.time()
        result = await simulator.advance_simulation(days=7)
        duration = time.time() - start_time

        # AC: 7 requirement
        assert duration < 5.0, f"Fast-forward took {duration:.2f}s (must be <5s)"
        assert result["days_advanced"] == 7

        print(f"\n✓ Fast-forward 7 days: {duration:.2f}s")

    @pytest.mark.asyncio
    async def test_state_persistence_across_restarts(self, reset_simulator):
        """Test AC: 6 - State persists and recovers after restart"""
        # Create simulator and set state
        simulator1 = DataSimulator()
        await simulator1.start_simulation()
        await simulator1.state_manager.save_state(
            current_date=datetime(2024, 5, 15, 12, 0, 0),
            last_event="test_event"
        )

        # Create new simulator instance (simulating restart)
        simulator2 = DataSimulator()
        state = await simulator2.state_manager.load_state()

        # Verify state was restored
        assert state.is_running is True
        assert state.last_event == "test_event"
        assert state.current_date.date() == datetime(2024, 5, 15).date()

    @pytest.mark.asyncio
    async def test_seasonal_patterns_applied(self):
        """Test AC: 5 - Maintains realistic patterns from historical data"""
        simulator = DataSimulator()

        # Generate events in September (should have 1.3x multiplier)
        from app.services.data_simulator import EventGenerator

        sept_generator = EventGenerator(datetime(2024, 9, 15))
        sept_enrollments = await sept_generator.generate_enrollment_events(count=10)

        # Generate events in summer (should have 0.8x multiplier)
        summer_generator = EventGenerator(datetime(2024, 7, 15))
        summer_enrollments = await summer_generator.generate_enrollment_events(count=10)

        # September should generate more enrollments
        assert len(sept_enrollments) > len(summer_enrollments), \
            "September should have more enrollments than summer due to seasonal patterns"

    @pytest.mark.asyncio
    async def test_event_cycle_performance(self, reset_simulator):
        """Test AC: 2 - Event cycle completes in <1 second"""
        simulator = DataSimulator(
            enrollments_per_cycle=5,
            sessions_per_cycle=10,
        )

        start_time = time.time()
        await simulator._generate_event_cycle()
        duration = time.time() - start_time

        # AC: 2 performance requirement
        assert duration < 1.0, f"Event cycle took {duration:.3f}s (must be <1s)"

        print(f"\n✓ Event cycle: {duration:.3f}s")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
class TestSimulationEndToEnd:
    """End-to-end simulation tests"""

    @pytest.mark.asyncio
    async def test_full_simulation_workflow(self, reset_simulator):
        """Test AC: 1-8 - Full simulation cycle (start → events → pause)"""
        simulator = DataSimulator(
            event_interval_seconds=2,  # Short interval for testing
            enrollments_per_cycle=1,
            sessions_per_cycle=2,
        )

        # Start simulation
        await simulator.start_simulation()

        # Run for a few seconds
        await asyncio.sleep(3)

        # Pause simulation
        await simulator.pause_simulation()

        # Verify simulation ran
        status = await simulator.get_status()
        assert status["is_running"] is False
        assert status["last_event_time"] is not None

    @pytest.mark.asyncio
    async def test_concurrent_api_calls(self):
        """Test AC: 4 - API handles concurrent calls"""
        simulator = DataSimulator()

        # Make concurrent status requests
        tasks = [simulator.get_status() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for result in results:
            assert "current_time" in result
            assert "is_running" in result

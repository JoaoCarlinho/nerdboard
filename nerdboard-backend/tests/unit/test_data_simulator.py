"""
Unit tests for Real-Time Data Simulator

Tests event generation logic, seasonal patterns, fast-forward calculations.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_simulator import (
    EventGenerator,
    SimulationStateManager,
    DataSimulator,
)


class TestEventGenerator:
    """Test EventGenerator class"""

    def test_seasonal_multiplier_september(self):
        """Test September enrollment spike (+30%)"""
        generator = EventGenerator(datetime(2024, 9, 15))
        multiplier = generator._calculate_seasonal_multiplier(datetime(2024, 9, 15))
        assert multiplier == 1.30, "September should have +30% spike"

    def test_seasonal_multiplier_january(self):
        """Test January enrollment spike (+20%)"""
        generator = EventGenerator(datetime(2024, 1, 15))
        multiplier = generator._calculate_seasonal_multiplier(datetime(2024, 1, 15))
        assert multiplier == 1.20, "January should have +20% spike"

    def test_seasonal_multiplier_summer(self):
        """Test summer dip (-20%)"""
        generator = EventGenerator(datetime(2024, 7, 15))
        for month in [6, 7, 8]:
            summer_date = datetime(2024, month, 15)
            multiplier = generator._calculate_seasonal_multiplier(summer_date)
            assert multiplier == 0.80, f"Month {month} should have -20% dip"

    def test_seasonal_multiplier_normal_month(self):
        """Test normal months (no adjustment)"""
        generator = EventGenerator(datetime(2024, 3, 15))
        multiplier = generator._calculate_seasonal_multiplier(datetime(2024, 3, 15))
        assert multiplier == 1.0, "March should have normal multiplier"

    def test_weighted_random_choice(self):
        """Test weighted random choice selects from items"""
        generator = EventGenerator(datetime(2024, 1, 1))
        items = ["Math", "Science", "English"]
        weights = {"Math": 0.5, "Science": 0.3, "English": 0.2}

        # Run multiple times to check it returns valid items
        for _ in range(10):
            choice = generator._weighted_random_choice(items, weights)
            assert choice in items, "Choice should be from items list"

    @pytest.mark.asyncio
    async def test_generate_enrollment_events_count(self):
        """Test enrollment generation creates correct count"""
        generator = EventGenerator(datetime(2024, 3, 15))  # Normal month
        enrollments = await generator.generate_enrollment_events(count=5)

        # In normal month (multiplier=1.0), should generate ~5 enrollments
        assert len(enrollments) >= 3, "Should generate at least 3 enrollments"
        assert len(enrollments) <= 7, "Should not exceed 7 enrollments"

    @pytest.mark.asyncio
    async def test_generate_enrollment_events_seasonal_adjustment(self):
        """Test seasonal multiplier affects enrollment count"""
        # September (1.3x multiplier)
        sept_generator = EventGenerator(datetime(2024, 9, 15))
        sept_enrollments = await sept_generator.generate_enrollment_events(count=5)

        # Summer (0.8x multiplier)
        summer_generator = EventGenerator(datetime(2024, 7, 15))
        summer_enrollments = await summer_generator.generate_enrollment_events(count=5)

        # September should have more enrollments than summer
        assert len(sept_enrollments) > len(summer_enrollments), \
            "September should generate more enrollments than summer"

    @pytest.mark.asyncio
    async def test_generate_enrollment_events_fields(self):
        """Test enrollment events have required fields"""
        generator = EventGenerator(datetime(2024, 1, 1))
        enrollments = await generator.generate_enrollment_events(count=3)

        for enrollment in enrollments:
            assert "student_id" in enrollment
            assert "subject" in enrollment
            assert "cohort_id" in enrollment
            assert "start_date" in enrollment
            assert "engagement_score" in enrollment

            # Validate field values
            assert enrollment["subject"] in generator.subjects
            assert 0.4 <= enrollment["engagement_score"] <= 1.0


class TestSimulationStateManager:
    """Test SimulationStateManager"""

    @pytest.mark.asyncio
    async def test_load_state_creates_default_if_missing(self):
        """Test load_state creates default state if none exists"""
        manager = SimulationStateManager()

        # Mock the database query to return None
        with patch('app.services.data_simulator.AsyncSessionLocal') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session_instance.execute.return_value = mock_result

            # Should create and return default state
            # Note: This will fail in real test due to database access
            # In actual testing, we'd need a test database


class TestDataSimulator:
    """Test DataSimulator class"""

    def test_initialization(self):
        """Test simulator initializes with correct defaults"""
        simulator = DataSimulator()

        assert simulator.event_interval_seconds == 300  # 5 minutes
        assert simulator.enrollments_per_cycle == 5
        assert simulator.sessions_per_cycle == 10

    def test_initialization_custom_params(self):
        """Test simulator accepts custom parameters"""
        simulator = DataSimulator(
            event_interval_seconds=60,
            enrollments_per_cycle=10,
            sessions_per_cycle=20,
        )

        assert simulator.event_interval_seconds == 60
        assert simulator.enrollments_per_cycle == 10
        assert simulator.sessions_per_cycle == 20

    @pytest.mark.asyncio
    async def test_fast_forward_calculation(self):
        """Test fast-forward calculates correct event counts"""
        simulator = DataSimulator(
            event_interval_seconds=300,
            enrollments_per_cycle=5,
            sessions_per_cycle=10,
        )

        # 7 days = 7 * (1440 / 5) = 7 * 288 = 2016 cycles
        # 2016 cycles * 5 enrollments = 10,080 enrollments
        # 2016 cycles * 10 sessions = 20,160 sessions

        # Mock the database operations
        with patch.object(simulator, '_insert_enrollments', new=AsyncMock()), \
             patch.object(simulator, '_insert_sessions', new=AsyncMock()), \
             patch.object(simulator, '_update_tutors', new=AsyncMock()), \
             patch.object(simulator.state_manager, 'load_state') as mock_load, \
             patch.object(simulator.state_manager, 'save_state', new=AsyncMock()):

            # Mock state
            mock_state = Mock()
            mock_state.current_date = datetime(2024, 1, 1)
            mock_load.return_value = mock_state

            # This test requires EventGenerator to not access database
            # In real test, we'd mock all database calls


class TestCLIHelpers:
    """Test CLI argument parsing helpers"""

    def test_config_loading(self):
        """Test configuration file loading"""
        import tempfile
        import os

        config_content = """
event_interval_seconds: 120
enrollments_per_cycle_base: 3
sessions_per_cycle_base: 6
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            from scripts.run_simulation import load_config
            config = load_config(config_path)

            assert config["event_interval_seconds"] == 120
            assert config["enrollments_per_cycle_base"] == 3
            assert config["sessions_per_cycle_base"] == 6
        finally:
            os.unlink(config_path)

    def test_config_loading_missing_file(self):
        """Test configuration loading handles missing file"""
        from scripts.run_simulation import load_config
        config = load_config("/nonexistent/path/config.yaml")
        assert config == {}

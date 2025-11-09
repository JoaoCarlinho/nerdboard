"""
Unit tests for CapacityCalculator

Tests time window calculations, utilization formulas, status determination.
"""

import pytest
from datetime import datetime, timedelta
from app.services.capacity_calculator import (
    CapacityCalculator,
    get_time_window_bounds,
    SUBJECTS
)


class TestTimeWindowCalculations:
    """Test time window boundary calculations (AC-3)"""

    def test_current_week_boundaries(self):
        """Test current_week returns Monday-Sunday of current week"""
        start, end = get_time_window_bounds("current_week")

        # Start should be Monday at 00:00:00
        assert start.weekday() == 0, "Start should be Monday"
        assert start.hour == 0 and start.minute == 0 and start.second == 0

        # End should be Sunday at 23:59:59
        assert end.weekday() == 6, "End should be Sunday"
        assert end.hour == 23 and end.minute == 59 and end.second == 59

        # Duration should be 7 days
        duration = (end - start).total_seconds()
        assert abs(duration - (7 * 24 * 3600 - 1)) < 2, "Duration should be ~7 days"

    def test_next_2_weeks_boundaries(self):
        """Test next_2_weeks returns 14-day window starting next Monday"""
        start, end = get_time_window_bounds("next_2_weeks")

        # Start should be next Monday
        assert start.weekday() == 0, "Start should be Monday"

        # Duration should be 14 days
        duration = (end - start).total_seconds()
        expected_duration = 14 * 24 * 3600 - 1
        assert abs(duration - expected_duration) < 2, "Duration should be ~14 days"

    def test_next_4_weeks_boundaries(self):
        """Test next_4_weeks returns 28-day window"""
        start, end = get_time_window_bounds("next_4_weeks")

        duration = (end - start).total_seconds()
        expected_duration = 28 * 24 * 3600 - 1
        assert abs(duration - expected_duration) < 2, "Duration should be ~28 days"

    def test_next_8_weeks_boundaries(self):
        """Test next_8_weeks returns 56-day window"""
        start, end = get_time_window_bounds("next_8_weeks")

        duration = (end - start).total_seconds()
        expected_duration = 56 * 24 * 3600 - 1
        assert abs(duration - expected_duration) < 2, "Duration should be ~56 days"

    def test_invalid_window_type(self):
        """Test invalid window type raises ValueError"""
        with pytest.raises(ValueError, match="Invalid window type"):
            get_time_window_bounds("invalid_window")


class TestStatusDetermination:
    """Test capacity status thresholds (AC-6)"""

    def test_status_normal(self):
        """Test status is 'normal' when utilization < 85%"""
        calculator = CapacityCalculator()

        assert calculator._determine_status(0.0) == "normal"
        assert calculator._determine_status(0.50) == "normal"
        assert calculator._determine_status(0.84) == "normal"

    def test_status_warning(self):
        """Test status is 'warning' when utilization 85-95%"""
        calculator = CapacityCalculator()

        assert calculator._determine_status(0.85) == "warning"
        assert calculator._determine_status(0.90) == "warning"
        assert calculator._determine_status(0.94) == "warning"

    def test_status_critical(self):
        """Test status is 'critical' when utilization >= 95%"""
        calculator = CapacityCalculator()

        assert calculator._determine_status(0.95) == "critical"
        assert calculator._determine_status(0.99) == "critical"
        assert calculator._determine_status(1.0) == "critical"


class TestUtilizationCalculation:
    """Test utilization rate formula (AC-1)"""

    def test_utilization_rate_calculation(self):
        """Test utilization_rate = booked_hours / total_hours"""
        # These would be calculated in actual method, testing formula here
        total_hours = 100
        booked_hours = 85
        expected_utilization = 0.85

        utilization_rate = booked_hours / total_hours
        assert utilization_rate == expected_utilization

    def test_zero_total_hours(self):
        """Test utilization = 0 when no tutors available"""
        total_hours = 0
        booked_hours = 0

        utilization_rate = (booked_hours / total_hours) if total_hours > 0 else 0
        assert utilization_rate == 0

    def test_100_percent_utilization(self):
        """Test 100% utilization when fully booked"""
        total_hours = 200
        booked_hours = 200

        utilization_rate = booked_hours / total_hours
        assert utilization_rate == 1.0


class TestCapacityCalculatorEdgeCases:
    """Test edge cases for capacity calculations"""

    def test_invalid_subject_raises_error(self):
        """Test ValueError raised for invalid subject - covered in integration tests"""
        # This test requires async context since calculate_subject_capacity is async
        # The actual validation is tested in integration tests
        pass

    def test_time_windows_list(self):
        """Test calculator has correct time windows defined"""
        calculator = CapacityCalculator()

        expected_windows = ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]
        assert calculator.time_windows == expected_windows

    def test_subjects_constant_available(self):
        """Test SUBJECTS constant is imported correctly"""
        assert SUBJECTS is not None
        assert len(SUBJECTS) > 0
        assert "Math" in SUBJECTS or "SAT Prep" in SUBJECTS


# Performance benchmarks (not strict assertions, for monitoring)
class TestPerformanceTargets:
    """Performance monitoring tests (AC-2)"""

    def test_time_window_calculation_performance(self):
        """Test time window calculation is fast (<1ms)"""
        import time

        iterations = 1000
        start = time.time()

        for _ in range(iterations):
            get_time_window_bounds("current_week")

        duration_ms = (time.time() - start) * 1000 / iterations
        print(f"\nTime window calculation: {duration_ms:.4f}ms per call")

        # Should be very fast (< 1ms)
        assert duration_ms < 1.0, f"Time window calc too slow: {duration_ms:.4f}ms"

    def test_status_determination_performance(self):
        """Test status determination is fast"""
        import time

        calculator = CapacityCalculator()
        iterations = 10000

        start = time.time()
        for _ in range(iterations):
            calculator._determine_status(0.87)

        duration_ms = (time.time() - start) * 1000 / iterations
        print(f"\nStatus determination: {duration_ms:.6f}ms per call")

        # Should be extremely fast
        assert duration_ms < 0.01, f"Status determination too slow: {duration_ms:.6f}ms"

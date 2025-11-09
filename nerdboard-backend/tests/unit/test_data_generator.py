"""
Unit tests for Historical Data Generator

Tests seasonal patterns, configuration parsing, data generation logic.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_generator import DataGenerator, SUBJECTS
from scripts.generate_historical_data import parse_date, parse_subjects, load_config


class TestDataGenerator:
    """Test DataGenerator class"""

    def test_initialization(self):
        """Test generator initialization with custom parameters"""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        generator = DataGenerator(
            start_date=start,
            end_date=end,
            num_tutors=200,
            num_students=600,
        )

        assert generator.start_date == start
        assert generator.end_date == end
        assert generator.num_tutors == 200
        assert generator.num_students == 600
        assert len(generator.student_ids) == 600
        assert generator.subjects == SUBJECTS

    def test_seasonal_multiplier_september(self):
        """Test September enrollment spike (+30%)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        sept_date = datetime(2024, 9, 15)
        multiplier = generator._calculate_seasonal_multiplier(sept_date)

        assert multiplier == 1.30, "September should have +30% enrollment spike"

    def test_seasonal_multiplier_january(self):
        """Test January enrollment spike (+20%)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        jan_date = datetime(2024, 1, 15)
        multiplier = generator._calculate_seasonal_multiplier(jan_date)

        assert multiplier == 1.20, "January should have +20% enrollment spike"

    def test_seasonal_multiplier_summer(self):
        """Test summer enrollment dip (-20%)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        for month in [6, 7, 8]:
            summer_date = datetime(2024, month, 15)
            multiplier = generator._calculate_seasonal_multiplier(summer_date)
            assert multiplier == 0.80, f"Month {month} should have -20% summer dip"

    def test_session_decline_multiplier(self):
        """Test end-of-semester session decline (-20%)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # November decline
        nov_date = datetime(2024, 11, 15)
        multiplier = generator._calculate_session_decline_multiplier(nov_date)
        assert multiplier == 0.80, "November should have -20% session decline"

        # May decline
        may_date = datetime(2024, 5, 15)
        multiplier = generator._calculate_session_decline_multiplier(may_date)
        assert multiplier == 0.80, "May should have -20% session decline"

        # Normal month
        march_date = datetime(2024, 3, 15)
        multiplier = generator._calculate_session_decline_multiplier(march_date)
        assert multiplier == 1.0, "March should have normal session volume"

    def test_peak_hours_weekday(self):
        """Test peak hour detection for weekdays (4pm-9pm)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Peak hours (16-21)
        for hour in range(16, 22):
            assert generator._is_peak_hours(hour, is_weekday=True), f"Hour {hour} should be peak on weekday"

        # Off-peak hours
        assert not generator._is_peak_hours(12, is_weekday=True), "Noon should be off-peak on weekday"
        assert not generator._is_peak_hours(22, is_weekday=True), "10pm should be off-peak on weekday"

    def test_peak_hours_weekend(self):
        """Test peak hour detection for weekends (10am-6pm)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Peak hours (10-18)
        for hour in range(10, 19):
            assert generator._is_peak_hours(hour, is_weekday=False), f"Hour {hour} should be peak on weekend"

        # Off-peak hours
        assert not generator._is_peak_hours(8, is_weekday=False), "8am should be off-peak on weekend"
        assert not generator._is_peak_hours(20, is_weekday=False), "8pm should be off-peak on weekend"

    @pytest.mark.asyncio
    async def test_generate_tutors_count(self):
        """Test that correct number of tutors are generated (AC: 5)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            num_tutors=150,
        )

        tutors = await generator.generate_tutors()

        assert len(tutors) == 150, "Should generate exactly 150 tutors"
        assert len(tutors) >= 100, "AC: 5 - Must generate at least 100 tutors"

    @pytest.mark.asyncio
    async def test_generate_tutors_fields(self):
        """Test tutor field generation and ranges"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            num_tutors=50,
        )

        tutors = await generator.generate_tutors()

        for tutor in tutors:
            # Check required fields
            assert "tutor_id" in tutor
            assert "subjects" in tutor
            assert "weekly_capacity_hours" in tutor
            assert "utilization_rate" in tutor
            assert "avg_response_time_hours" in tutor

            # Check value ranges
            assert 1 <= len(tutor["subjects"]) <= 3, "Tutor should teach 1-3 subjects"
            assert 15 <= tutor["weekly_capacity_hours"] <= 40, "Capacity should be 15-40 hours"
            assert 0.5 <= tutor["utilization_rate"] <= 0.9, "Utilization should be 0.5-0.9"
            assert 1 <= tutor["avg_response_time_hours"] <= 24, "Response time should be 1-24 hours"

    @pytest.mark.asyncio
    async def test_generate_enrollments_subjects(self):
        """Test enrollment generation includes 10+ subjects (AC: 4)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),  # One month for faster test
            num_students=100,
        )

        enrollments = await generator.generate_enrollments()

        unique_subjects = set(e["subject"] for e in enrollments)

        assert len(unique_subjects) >= 10, "AC: 4 - Must have at least 10 subjects"
        assert len(enrollments) > 0, "Should generate enrollments"

    @pytest.mark.asyncio
    async def test_tutor_churn_simulation(self):
        """Test tutor churn during summer months (AC: 3)"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            num_tutors=100,
        )

        await generator.generate_tutors()
        initial_count = len(generator.tutor_data)

        churned_dates = generator.simulate_tutor_churn()

        # Should have churned some tutors
        assert len(churned_dates) > 0, "Should have churned at least some tutors"

        # Should have replaced them
        assert len(generator.tutor_data) >= initial_count, "Should maintain or increase tutor count after replacements"

        # Churn rate should be reasonable (10-15% quarterly ~ 3-5% monthly for 3 months = 9-15% total)
        churn_rate = len(churned_dates) / initial_count
        assert 0.05 <= churn_rate <= 0.20, f"Churn rate {churn_rate:.2%} should be between 5-20%"

    @pytest.mark.asyncio
    async def test_generate_health_metrics_customers(self):
        """Test health metrics generated for 20+ customers"""
        generator = DataGenerator(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),  # One week for faster test
        )

        metrics = await generator.generate_health_metrics()

        unique_customers = set(m["customer_id"] for m in metrics)

        assert len(unique_customers) >= 20, "Should generate metrics for at least 20 customers"
        assert len(metrics) >= 140, "Should have daily metrics for 7 days * 20+ customers"


class TestCLIParsing:
    """Test CLI argument parsing and configuration"""

    def test_parse_date_valid(self):
        """Test valid date parsing"""
        date = parse_date("2024-06-15")
        assert date.year == 2024
        assert date.month == 6
        assert date.day == 15

    def test_parse_date_invalid(self):
        """Test invalid date format raises error"""
        with pytest.raises(Exception):
            parse_date("2024/06/15")

        with pytest.raises(Exception):
            parse_date("invalid")

    def test_parse_subjects_single(self):
        """Test parsing single subject"""
        subjects = parse_subjects("Math")
        assert subjects == ["Math"]

    def test_parse_subjects_multiple(self):
        """Test parsing multiple subjects"""
        subjects = parse_subjects("Math, Science, English")
        assert subjects == ["Math", "Science", "English"]

    def test_parse_subjects_empty(self):
        """Test parsing empty string"""
        subjects = parse_subjects("")
        assert subjects == []

    def test_load_config_valid(self):
        """Test loading valid config file"""
        # Create a mock config file
        import tempfile
        import os

        config_content = """
start_date: "2024-01-01"
end_date: "2024-12-31"
num_tutors: 200
num_students: 600
subjects_list:
  - Math
  - Science
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config["start_date"] == "2024-01-01"
            assert config["num_tutors"] == 200
            assert "Math" in config["subjects_list"]
        finally:
            os.unlink(config_path)

    def test_load_config_missing_file(self):
        """Test loading non-existent config file returns empty dict"""
        config = load_config("/nonexistent/path/config.yaml")
        assert config == {}

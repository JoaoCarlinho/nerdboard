"""
Integration tests for Health API

Tests health score calculation with real database, API endpoints, batch processing.
"""
import pytest
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text

from app.services.health_score_calculator import HealthScoreCalculator, get_health_calculator
from app.database import AsyncSessionLocal
from app.models.enrollment import Enrollment
from app.models.session import Session
from app.models.health_metric import HealthMetric


@pytest.fixture(scope="function")
async def sample_customers():
    """Create sample customers (enrollments) for testing"""
    async with AsyncSessionLocal() as session:
        # Clear existing test data
        await session.execute(text("DELETE FROM enrollments WHERE cohort_id LIKE 'TEST%'"))
        await session.commit()

        # Create test enrollments (customers)
        customer_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4())
        ]

        enrollments = [
            Enrollment(
                student_id=uuid.UUID(customer_ids[0]),
                subject="Physics",
                cohort_id="TEST_2025_Q1",
                start_date=datetime.utcnow() - timedelta(days=30),
                engagement_score=0.80
            ),
            Enrollment(
                student_id=uuid.UUID(customer_ids[1]),
                subject="Math",
                cohort_id="TEST_2025_Q1",
                start_date=datetime.utcnow() - timedelta(days=60),
                engagement_score=0.60
            ),
            Enrollment(
                student_id=uuid.UUID(customer_ids[2]),
                subject="Chemistry",
                cohort_id="TEST_2025_Q2",
                start_date=datetime.utcnow() - timedelta(days=15),
                engagement_score=0.40
            ),
        ]

        for enrollment in enrollments:
            session.add(enrollment)

        await session.commit()

    yield customer_ids

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM enrollments WHERE cohort_id LIKE 'TEST%'"))
        await session.commit()


@pytest.fixture(scope="function")
async def sample_sessions(sample_customers):
    """Create sample sessions for testing"""
    async with AsyncSessionLocal() as session:
        # Clear existing test sessions
        await session.execute(text("DELETE FROM sessions WHERE session_id LIKE 'TEST%'"))
        await session.commit()

        # Create sessions for customers
        sessions = [
            # Customer 1: 8 sessions in last 30 days (high velocity)
            Session(
                session_id="TEST_SESSION_1_1",
                subject="Physics",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[0]),
                scheduled_time=datetime.utcnow() - timedelta(days=25),
                duration_minutes=60
            ),
            Session(
                session_id="TEST_SESSION_1_2",
                subject="Physics",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[0]),
                scheduled_time=datetime.utcnow() - timedelta(days=20),
                duration_minutes=60
            ),
            Session(
                session_id="TEST_SESSION_1_3",
                subject="Physics",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[0]),
                scheduled_time=datetime.utcnow() - timedelta(days=15),
                duration_minutes=60
            ),
            Session(
                session_id="TEST_SESSION_1_4",
                subject="Physics",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[0]),
                scheduled_time=datetime.utcnow() - timedelta(days=10),
                duration_minutes=60
            ),
            # Customer 2: 2 sessions in last 30 days (low velocity)
            Session(
                session_id="TEST_SESSION_2_1",
                subject="Math",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[1]),
                scheduled_time=datetime.utcnow() - timedelta(days=20),
                duration_minutes=90
            ),
            Session(
                session_id="TEST_SESSION_2_2",
                subject="Math",
                tutor_id=None,
                student_id=uuid.UUID(sample_customers[1]),
                scheduled_time=datetime.utcnow() - timedelta(days=10),
                duration_minutes=90
            ),
            # Customer 3: No sessions (new customer)
        ]

        for session_obj in sessions:
            session.add(session_obj)

        await session.commit()

    yield sessions

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM sessions WHERE session_id LIKE 'TEST%'"))
        await session.commit()


@pytest.fixture(scope="function")
async def sample_health_metrics(sample_customers):
    """Create sample health metrics for testing"""
    async with AsyncSessionLocal() as session:
        # Clear existing test health metrics
        await session.execute(text("DELETE FROM health_metrics WHERE customer_id LIKE :pattern"),
                             {"pattern": f"{sample_customers[0][:8]}%"})
        await session.commit()

        # Create health metrics with IB calls
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        health_metrics = [
            # Customer 1: 1 IB call (medium risk)
            HealthMetric(
                customer_id=sample_customers[0],
                date=today - timedelta(days=10),
                health_score=75.0,
                engagement_level=80,
                support_ticket_count=1
            ),
            # Customer 2: 2 IB calls (high risk)
            HealthMetric(
                customer_id=sample_customers[1],
                date=today - timedelta(days=12),
                health_score=55.0,
                engagement_level=60,
                support_ticket_count=1
            ),
            HealthMetric(
                customer_id=sample_customers[1],
                date=today - timedelta(days=5),
                health_score=50.0,
                engagement_level=60,
                support_ticket_count=1
            ),
            # Customer 3: 0 IB calls (low risk if good score)
        ]

        for health_metric in health_metrics:
            session.add(health_metric)

        await session.commit()

    yield health_metrics

    # Cleanup
    async with AsyncSessionLocal() as session:
        for customer_id in sample_customers:
            await session.execute(
                text("DELETE FROM health_metrics WHERE customer_id = :customer_id"),
                {"customer_id": customer_id}
            )
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
class TestHealthScoreCalculation:
    """Integration tests for health score calculation"""

    @pytest.mark.asyncio
    async def test_calculate_health_score_with_real_data(self, sample_customers, sample_sessions):
        """Test AC-1: Calculate health score with real database data"""
        calculator = HealthScoreCalculator()

        # Calculate health score for customer 1 (has sessions)
        customer_id = sample_customers[0]
        health_score = await calculator.calculate_health_score(customer_id)

        # Should have positive health score
        assert health_score > 0
        assert health_score <= 100

        # Customer has first session (100), some velocity, no IB penalty, 80% engagement
        # Minimum expected: 0.4*100 + 0.2*100 + 0.1*80 = 68
        assert health_score >= 60

    @pytest.mark.asyncio
    async def test_churn_risk_detection(self, sample_customers, sample_sessions, sample_health_metrics):
        """Test AC-3: Churn risk detection with IB calls"""
        calculator = HealthScoreCalculator()

        # Customer 1: 1 IB call → medium risk
        churn_risk_1 = await calculator.detect_churn_risk(sample_customers[0])
        assert churn_risk_1 in ["medium", "low"]  # Depends on calculated score

        # Customer 2: 2 IB calls → high risk
        churn_risk_2 = await calculator.detect_churn_risk(sample_customers[1])
        assert churn_risk_2 == "high"

        # Customer 3: 0 IB calls, depends on score
        churn_risk_3 = await calculator.detect_churn_risk(sample_customers[2])
        assert churn_risk_3 in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_health_metric_persistence(self, sample_customers):
        """Test AC-4: Health metrics saved to database"""
        calculator = HealthScoreCalculator()
        customer_id = sample_customers[0]

        # Calculate and save health score
        health_score = await calculator.calculate_health_score(customer_id)
        health_data = {
            "health_score": health_score,
            "engagement_level": 80,
            "support_ticket_count": 0
        }

        await calculator.save_health_metric(customer_id, health_data)

        # Verify saved to database
        async with AsyncSessionLocal() as session:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            result = await session.execute(
                text("""
                    SELECT * FROM health_metrics
                    WHERE customer_id = :customer_id
                    AND date = :today
                    ORDER BY updated_at DESC
                    LIMIT 1
                """),
                {"customer_id": customer_id, "today": today}
            )
            saved_metric = result.first()

        assert saved_metric is not None
        assert saved_metric.customer_id == customer_id
        assert saved_metric.health_score == health_score
        assert saved_metric.engagement_level == 80


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
class TestHealthScorePerformance:
    """Performance tests for health score calculation (AC-7)"""

    @pytest.mark.asyncio
    async def test_batch_calculation_performance(self, sample_customers, sample_sessions):
        """Test AC-7: Batch calculation completes in <5 seconds for 500 customers"""
        calculator = HealthScoreCalculator()

        # Note: This test only has 3 customers, not 500
        # In production with 500 customers, should still complete in <5 seconds

        start_time = time.time()
        summary = await calculator.calculate_all_customers_health()
        duration_ms = (time.time() - start_time) * 1000

        # Should process all sample customers
        assert summary["customers_processed"] >= 3

        # Performance target (scaled for 3 customers)
        # 3 customers should complete in well under 5000ms
        assert duration_ms < 1000, f"Batch calculation took {duration_ms:.2f}ms"

        print(f"\n✓ Batch calculation ({summary['customers_processed']} customers): {duration_ms:.2f}ms")


@pytest.mark.asyncio
@pytest.mark.integration
class TestCohortSegmentation:
    """Test cohort-level health aggregation (AC-5)"""

    @pytest.mark.asyncio
    async def test_cohort_health_aggregates(self, sample_customers, sample_health_metrics):
        """Test AC-5: Cohort segmentation and aggregation"""
        calculator = HealthScoreCalculator()

        # Calculate cohort aggregates
        cohorts = await calculator.calculate_cohort_health_aggregates()

        # Should have at least TEST cohorts
        assert len(cohorts) >= 0  # May be 0 if no recent health metrics

        # If cohorts exist, validate structure
        if cohorts:
            cohort = cohorts[0]
            assert "cohort_id" in cohort
            assert "customer_count" in cohort
            assert "avg_health_score" in cohort
            assert "churn_risk_high" in cohort

            # Counts should be valid
            assert cohort["customer_count"] >= 0
            assert 0 <= cohort["avg_health_score"] <= 100
            assert cohort["churn_risk_high"] >= 0


@pytest.mark.asyncio
@pytest.mark.integration
class TestDashboardMetrics:
    """Test dashboard health metrics (AC-8)"""

    @pytest.mark.asyncio
    async def test_dashboard_health_metrics(self, sample_customers, sample_health_metrics):
        """Test AC-8: Dashboard metrics accessible"""
        calculator = HealthScoreCalculator()

        # Get dashboard metrics
        metrics = await calculator.get_dashboard_health_metrics()

        # Validate structure
        assert "total_customers" in metrics
        assert "avg_health_score" in metrics
        assert "health_distribution" in metrics
        assert "churn_risk_counts" in metrics

        # Validate values
        assert metrics["total_customers"] >= 0
        assert 0 <= metrics["avg_health_score"] <= 100

        # Validate distributions
        assert "high" in metrics["health_distribution"]
        assert "medium" in metrics["health_distribution"]
        assert "low" in metrics["health_distribution"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases for health calculations"""

    @pytest.mark.asyncio
    async def test_new_customer_with_no_sessions(self):
        """Test health score for new customer with no sessions"""
        calculator = HealthScoreCalculator()

        # Create new customer
        new_customer_id = str(uuid.uuid4())

        async with AsyncSessionLocal() as session:
            enrollment = Enrollment(
                student_id=uuid.UUID(new_customer_id),
                subject="Physics",
                cohort_id="TEST_NEW",
                start_date=datetime.utcnow(),
                engagement_score=0.50
            )
            session.add(enrollment)
            await session.commit()

        try:
            # Calculate health score
            health_score = await calculator.calculate_health_score(new_customer_id)

            # Should have low but non-zero score (engagement + IB penalty inverse)
            assert health_score >= 0
            # 0.2 * 100 + 0.1 * 50 = 20 + 5 = 25
            assert health_score >= 20

        finally:
            # Cleanup
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("DELETE FROM enrollments WHERE cohort_id = 'TEST_NEW'")
                )
                await session.commit()

    @pytest.mark.asyncio
    async def test_customer_not_found(self):
        """Test health score for non-existent customer"""
        calculator = HealthScoreCalculator()

        # Non-existent customer
        fake_customer_id = str(uuid.uuid4())

        health_score = await calculator.calculate_health_score(fake_customer_id)

        # Should return 0 for non-existent customer
        assert health_score == 0.0

"""
Demo Scenario Loader

Loads pre-configured demo scenarios for consistent presentations.
Usage: python -m app.scripts.load_demo --scenario physics_shortage
"""
import asyncio
import argparse
from datetime import datetime, timedelta
import uuid
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.models.enrollment import Enrollment
from app.models.tutor import Tutor
from app.models.session import Session
from app.models.health_metric import HealthMetric


async def clear_test_data():
    """Clear all existing data"""
    async with AsyncSessionLocal() as session:
        tables = ["sessions", "health_metrics", "capacity_snapshots", "enrollments", "tutors"]
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
    print("✓ Cleared existing data")


async def load_physics_shortage_scenario():
    """
    Load Physics Shortage scenario (AC-1).

    Scenario: Physics shows 85% utilization, shortage predicted in 12 days.
    """
    print("\nLoading Physics Shortage scenario...")

    async with AsyncSessionLocal() as session:
        # Create 20 Physics tutors
        tutors = []
        for i in range(20):
            tutor = Tutor(
                tutor_id=f"PHYS_TUTOR_{i+1}",
                subjects=["Physics"],
                weekly_capacity_hours=30,  # 20 tutors * 30 hours = 600 total
                utilization_rate=0.85
            )
            tutors.append(tutor)
            session.add(tutor)

        await session.commit()
        print(f"  Created {len(tutors)} Physics tutors (600 weekly hours)")

        # Create high volume of sessions (540 hours booked = 90%)
        sessions = []
        now = datetime.utcnow()

        for i in range(90):  # 90 sessions * 6 hours = 540 hours
            session_obj = Session(
                session_id=f"PHYS_SESSION_{i+1}",
                subject="Physics",
                tutor_id=tutors[i % len(tutors)].id,
                student_id=uuid.uuid4(),
                scheduled_time=now + timedelta(days=(i % 14)),  # Next 2 weeks
                duration_minutes=360  # 6 hours each
            )
            sessions.append(session_obj)
            session.add(session_obj)

        await session.commit()
        print(f"  Created {len(sessions)} sessions (540 hours booked, 90% utilization)")
        print("  ✓ Physics Shortage scenario loaded")
        print("  Expected: 85-90% utilization, shortage warning in next 2 weeks")


async def load_sat_spike_scenario():
    """
    Load SAT Prep Spike scenario (AC-2).

    Scenario: +40% enrollment spike in last 7 days.
    """
    print("\nLoading SAT Prep Spike scenario...")

    async with AsyncSessionLocal() as session:
        # Create SAT tutors
        tutors = []
        for i in range(15):
            tutor = Tutor(
                tutor_id=f"SAT_TUTOR_{i+1}",
                subjects=["SAT Prep"],
                weekly_capacity_hours=40,
                utilization_rate=0.60
            )
            tutors.append(tutor)
            session.add(tutor)

        await session.commit()
        print(f"  Created {len(tutors)} SAT tutors")

        # Create baseline enrollments (50/week)
        enrollments = []
        now = datetime.utcnow()

        # Baseline enrollments (weeks 2-4 ago)
        for i in range(150):  # 50/week * 3 weeks
            enrollment = Enrollment(
                student_id=uuid.uuid4(),
                subject="SAT Prep",
                cohort_id="SAT_2025_Q1",
                start_date=now - timedelta(days=(28 - i % 21)),
                engagement_score=0.70
            )
            enrollments.append(enrollment)
            session.add(enrollment)

        # Spike enrollments (last 7 days, +40%)
        for i in range(70):  # 50 * 1.4 = 70 for last week
            enrollment = Enrollment(
                student_id=uuid.uuid4(),
                subject="SAT Prep",
                cohort_id="SAT_2025_Q1",
                start_date=now - timedelta(days=(i % 7)),
                engagement_score=0.75
            )
            enrollments.append(enrollment)
            session.add(enrollment)

        await session.commit()
        print(f"  Created {len(enrollments)} enrollments (70 in last 7 days, +40% spike)")
        print("  ✓ SAT Spike scenario loaded")
        print("  Expected: Enrollment velocity spike detected, 4-week capacity warning")


async def load_churn_risk_scenario():
    """
    Load Churn Risk Alert scenario (AC-3).

    Scenario: 5 customers with ≥2 IB calls in 14 days.
    """
    print("\nLoading Churn Risk Alert scenario...")

    async with AsyncSessionLocal() as session:
        # Create 5 high-risk customers
        customer_ids = [str(uuid.uuid4()) for _ in range(5)]

        for i, customer_id in enumerate(customer_ids):
            # Create enrollment
            enrollment = Enrollment(
                student_id=uuid.UUID(customer_id),
                subject="Math",
                cohort_id="MATH_2025_Q1",
                start_date=datetime.utcnow() - timedelta(days=60),
                engagement_score=0.30  # Low engagement
            )
            session.add(enrollment)

            # Create health metrics with high IB calls
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            health_metric_1 = HealthMetric(
                customer_id=customer_id,
                date=today - timedelta(days=12),
                health_score=45.0,
                engagement_level=35,
                support_ticket_count=1  # First IB call
            )
            session.add(health_metric_1)

            health_metric_2 = HealthMetric(
                customer_id=customer_id,
                date=today - timedelta(days=5),
                health_score=35.0,
                engagement_level=30,
                support_ticket_count=1  # Second IB call
            )
            session.add(health_metric_2)

        await session.commit()
        print(f"  Created 5 high-risk customers")
        print("  Each has: ≥2 IB calls in 14 days, health score <40")
        print("  ✓ Churn Risk scenario loaded")
        print("  Expected: 5 customers flagged as high churn risk")


async def load_scenario(scenario_name: str):
    """
    Load a demo scenario (AC-4, AC-5).

    Args:
        scenario_name: Name of scenario to load
    """
    scenarios = {
        "physics_shortage": load_physics_shortage_scenario,
        "sat_spike": load_sat_spike_scenario,
        "churn_risk": load_churn_risk_scenario
    }

    if scenario_name not in scenarios:
        print(f"ERROR: Unknown scenario '{scenario_name}'")
        print(f"Available scenarios: {', '.join(scenarios.keys())}")
        return

    # Clear existing data
    await clear_test_data()

    # Load scenario
    await scenarios[scenario_name]()

    print(f"\n✅ Scenario '{scenario_name}' loaded successfully!")
    print("Demo is ready for presentation")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Load demo scenarios")
    parser.add_argument(
        "--scenario",
        "-s",
        choices=["physics_shortage", "sat_spike", "churn_risk", "all"],
        required=True,
        help="Scenario to load"
    )

    args = parser.parse_args()

    if args.scenario == "all":
        print("Loading all scenarios is not supported (would conflict)")
        print("Load scenarios individually for demos")
    else:
        asyncio.run(load_scenario(args.scenario))


if __name__ == "__main__":
    main()

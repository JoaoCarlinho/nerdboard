"""
Historical Data Generator Service

Generates 12 months of realistic historical data for the nerdboard platform.
Implements seasonal patterns, batch inserts, and async processing for performance.
"""

import asyncio
import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from faker import Faker

from app.database import AsyncSessionLocal
from app.models.enrollment import Enrollment
from app.models.tutor import Tutor
from app.models.session import Session
from app.models.health_metric import HealthMetric
from app.models.capacity_snapshot import CapacitySnapshot
from app.models.simulation_state import SimulationState
from app.models.data_quality_log import DataQualityLog

# Initialize Faker for realistic data generation
fake = Faker()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Subject configuration - 10+ subjects as per AC: 4
SUBJECTS = [
    "Math",
    "Science",
    "English",
    "History",
    "Computer Science",
    "Languages",
    "Arts",
    "Music",
    "Economics",
    "Biology",
    "SAT Prep",
    "Physics",
    "Chemistry",
]

# Subject distribution weights (30% SAT, 25% Math, 20% Science, 25% other)
SUBJECT_WEIGHTS = {
    "SAT Prep": 0.30,
    "Math": 0.25,
    "Science": 0.10,
    "Physics": 0.05,
    "Chemistry": 0.05,
    "English": 0.08,
    "History": 0.05,
    "Computer Science": 0.04,
    "Languages": 0.03,
    "Arts": 0.02,
    "Music": 0.02,
    "Economics": 0.01,
    "Biology": 0.05,
}


class DataGenerator:
    """Main data generator class"""

    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        num_tutors: int = 150,
        num_students: int = 500,
        subjects_list: List[str] = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.num_tutors = num_tutors
        self.num_students = num_students
        self.subjects = subjects_list or SUBJECTS

        # Pre-generate UUIDs for performance (AC: 7 optimization)
        self.student_ids = [uuid.uuid4() for _ in range(num_students)]
        self.tutor_data = []
        self.enrollment_data = []
        self.session_data = []
        self.health_metric_data = []
        self.capacity_snapshot_data = []

        logger.info(
            f"Initialized DataGenerator: {start_date.date()} to {end_date.date()}, "
            f"{num_tutors} tutors, {num_students} students, {len(self.subjects)} subjects"
        )

    def _weighted_random_choice(self, items: List[str], weights: Dict[str, float] = None) -> str:
        """Select random item with optional weights"""
        if weights and all(item in weights for item in items):
            return random.choices(items, weights=[weights[item] for item in items])[0]
        return random.choice(items)

    def _calculate_seasonal_multiplier(self, date: datetime) -> float:
        """Calculate enrollment multiplier based on seasonal patterns (AC: 3)"""
        month = date.month

        # September spike: +30%
        if month == 9:
            return 1.30
        # January spike: +20%
        elif month == 1:
            return 1.20
        # Summer dip: -20% (June-August)
        elif month in [6, 7, 8]:
            return 0.80
        # Normal months
        else:
            return 1.0

    def _calculate_session_decline_multiplier(self, date: datetime) -> float:
        """Calculate session volume multiplier for end-of-semester decline (AC: 3)"""
        month = date.month

        # November and May: -20% session volume
        if month in [11, 5]:
            return 0.80
        else:
            return 1.0

    def _is_peak_hours(self, hour: int, is_weekday: bool) -> bool:
        """Determine if hour is peak tutoring time"""
        if is_weekday:
            # Weekday peak: 4pm-9pm (16-21)
            return 16 <= hour <= 21
        else:
            # Weekend peak: 10am-6pm (10-18)
            return 10 <= hour <= 18

    def _generate_realistic_time(self, date: datetime, is_weekday: bool) -> datetime:
        """Generate realistic session time with peak hour weighting"""
        # 70% chance of peak hours, 30% chance of off-peak
        if random.random() < 0.7:
            if is_weekday:
                hour = random.randint(16, 21)
            else:
                hour = random.randint(10, 18)
        else:
            # Off-peak hours
            hour = random.randint(8, 22)

        minute = random.choice([0, 15, 30, 45])  # Sessions start on quarter hours
        return date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    async def generate_tutors(self) -> List[Dict[str, Any]]:
        """Generate tutor records (AC: 5 - minimum 100 tutors)"""
        logger.info(f"Generating {self.num_tutors} tutors...")

        tutors = []
        for i in range(self.num_tutors):
            # Each tutor teaches 1-3 subjects
            num_subjects = random.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
            tutor_subjects = random.sample(self.subjects, num_subjects)

            # Weekly capacity: 15-40 hours, weighted toward 20-30
            capacity_hours = int(random.triangular(15, 40, 25))

            # Utilization rate: 0.5-0.9, weighted toward 0.7-0.8
            utilization = random.triangular(0.5, 0.9, 0.75)

            # Response time: 1-24 hours, weighted toward 4-8
            response_time = random.triangular(1, 24, 6)

            tutor = {
                "tutor_id": f"T{i+1:04d}",
                "subjects": tutor_subjects,
                "weekly_capacity_hours": capacity_hours,
                "utilization_rate": round(utilization, 2),
                "avg_response_time_hours": round(response_time, 1),
            }
            tutors.append(tutor)

        self.tutor_data = tutors
        logger.info(f"Generated {len(tutors)} tutor records")
        return tutors

    async def generate_enrollments(self) -> List[Dict[str, Any]]:
        """Generate enrollment records with seasonal patterns (AC: 3, 4)"""
        logger.info(f"Generating enrollments for {self.num_students} students across {len(self.subjects)} subjects...")

        enrollments = []
        current_date = self.start_date

        # Track enrollments to ensure distribution across subjects
        subject_counts = {subject: 0 for subject in self.subjects}

        while current_date <= self.end_date:
            # Calculate seasonal multiplier
            multiplier = self._calculate_seasonal_multiplier(current_date)

            # Base enrollments per day: ~5, adjusted by season
            daily_enrollments = int(5 * multiplier)

            for _ in range(daily_enrollments):
                student_id = random.choice(self.student_ids)
                subject = self._weighted_random_choice(self.subjects, SUBJECT_WEIGHTS)
                subject_counts[subject] += 1

                # Generate cohort_id with realistic pattern
                semester = "fall" if current_date.month >= 8 else "spring"
                year = current_date.year
                course_num = random.choice([101, 201, 301, "AP"])
                cohort_id = f"{year}-{semester}-{subject.lower().replace(' ', '-')}-{course_num}"

                # Engagement score: 0.4-1.0, weighted toward 0.6-0.8
                engagement = random.triangular(0.4, 1.0, 0.7)

                enrollment = {
                    "student_id": student_id,
                    "subject": subject,
                    "cohort_id": cohort_id,
                    "start_date": current_date,
                    "engagement_score": round(engagement, 2),
                }
                enrollments.append(enrollment)

            current_date += timedelta(days=1)

        self.enrollment_data = enrollments
        logger.info(f"Generated {len(enrollments)} enrollment records")
        logger.info(f"Subject distribution: {subject_counts}")
        return enrollments

    async def generate_sessions(self, churned_tutor_dates: Dict[str, datetime]) -> List[Dict[str, Any]]:
        """Generate tutoring sessions with realistic patterns (AC: 6 - minimum 10,000 sessions)"""
        logger.info("Generating tutoring sessions...")

        sessions = []
        target_sessions = max(10000, len(self.enrollment_data) * 8)  # Ensure minimum 10,000

        sessions_per_day = target_sessions // ((self.end_date - self.start_date).days + 1)

        current_date = self.start_date
        session_id_counter = 1

        while current_date <= self.end_date and len(sessions) < target_sessions:
            # Apply session decline multiplier
            decline_mult = self._calculate_session_decline_multiplier(current_date)
            daily_sessions = int(sessions_per_day * decline_mult)

            is_weekday = current_date.weekday() < 5

            for _ in range(daily_sessions):
                # Select a random enrollment
                if not self.enrollment_data:
                    break

                enrollment = random.choice(self.enrollment_data)

                # Find available tutor for this subject
                available_tutors = [
                    t for t in self.tutor_data
                    if enrollment["subject"] in t["subjects"]
                    and (
                        t["tutor_id"] not in churned_tutor_dates
                        or churned_tutor_dates[t["tutor_id"]] > current_date
                    )
                ]

                if not available_tutors:
                    continue

                tutor = random.choice(available_tutors)

                # Generate realistic time
                scheduled_time = self._generate_realistic_time(current_date, is_weekday)

                # Duration: 30-120 minutes, weighted by subject
                # SAT/Test Prep tends to be longer
                if "SAT" in enrollment["subject"] or "Prep" in enrollment["subject"]:
                    duration = random.choice([60, 90, 120])
                else:
                    duration = random.choice([30, 45, 60, 90])

                session = {
                    "session_id": f"S{session_id_counter:06d}",
                    "subject": enrollment["subject"],
                    "tutor_id": tutor["tutor_id"],
                    "student_id": enrollment["student_id"],
                    "scheduled_time": scheduled_time,
                    "duration_minutes": duration,
                }
                sessions.append(session)
                session_id_counter += 1

            current_date += timedelta(days=1)

        self.session_data = sessions
        logger.info(f"Generated {len(sessions)} session records")
        return sessions

    def simulate_tutor_churn(self) -> Dict[str, datetime]:
        """Simulate tutor churn during summer months (AC: 3)"""
        logger.info("Simulating tutor churn...")

        churned_tutors = {}
        summer_months = [6, 7, 8]

        # Calculate summer period dates
        current_date = self.start_date
        while current_date <= self.end_date:
            if current_date.month in summer_months:
                # 10-15% quarterly turnover = ~3-5% monthly during summer
                churn_rate = random.uniform(0.03, 0.05)
                num_to_churn = int(self.num_tutors * churn_rate)

                # Select random tutors to churn (who haven't already churned)
                available_tutors = [t for t in self.tutor_data if t["tutor_id"] not in churned_tutors]
                if available_tutors:
                    tutors_to_churn = random.sample(available_tutors, min(num_to_churn, len(available_tutors)))

                    for tutor in tutors_to_churn:
                        churn_date = current_date + timedelta(days=random.randint(0, 28))
                        churned_tutors[tutor["tutor_id"]] = churn_date

                        # Add replacement tutor
                        new_tutor = {
                            "tutor_id": f"T{len(self.tutor_data)+1:04d}",
                            "subjects": tutor["subjects"],
                            "weekly_capacity_hours": tutor["weekly_capacity_hours"],
                            "utilization_rate": round(random.triangular(0.5, 0.9, 0.75), 2),
                            "avg_response_time_hours": round(random.triangular(1, 24, 6), 1),
                        }
                        self.tutor_data.append(new_tutor)

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)

        logger.info(f"Simulated {len(churned_tutors)} tutor churns, added {len(churned_tutors)} replacements")
        return churned_tutors

    async def generate_health_metrics(self) -> List[Dict[str, Any]]:
        """Generate daily health metrics for customers (AC: 3)"""
        logger.info("Generating health metrics...")

        metrics = []
        num_customers = 25  # 20+ customers
        customer_ids = [f"C{i+1:03d}" for i in range(num_customers)]

        # Track trends for at-risk customers (30% of customers)
        at_risk_customers = random.sample(customer_ids, int(num_customers * 0.3))

        current_date = self.start_date
        while current_date <= self.end_date:
            for customer_id in customer_ids:
                # Base health score calculation
                base_health = random.triangular(60, 100, 80)

                # Apply declining trend for at-risk customers
                if customer_id in at_risk_customers:
                    days_elapsed = (current_date - self.start_date).days
                    decline_rate = 0.05  # 5% decline per month
                    months_elapsed = days_elapsed / 30
                    base_health *= (1 - decline_rate * months_elapsed)
                    base_health = max(base_health, 40)  # Floor at 40

                # Engagement level: 1-10, weighted toward 6-8
                engagement = int(random.triangular(1, 10, 7))

                # Support tickets: 0-10, weighted toward 1-3
                tickets = int(random.triangular(0, 10, 2))

                # Session completion rate: 0.7-1.0, weighted toward 0.85-0.95
                completion_rate = random.triangular(0.7, 1.0, 0.9)

                metric = {
                    "customer_id": customer_id,
                    "date": current_date,
                    "health_score": round(base_health, 1),
                    "engagement_level": engagement,
                    "support_ticket_count": tickets,
                    "session_completion_rate": round(completion_rate, 2),
                }
                metrics.append(metric)

            current_date += timedelta(days=1)

        self.health_metric_data = metrics
        logger.info(f"Generated {len(metrics)} health metric records for {num_customers} customers")
        return metrics

    async def generate_capacity_snapshots(self) -> List[Dict[str, Any]]:
        """Generate daily capacity snapshots per subject"""
        logger.info("Generating capacity snapshots...")

        snapshots = []
        current_date = self.start_date

        while current_date <= self.end_date:
            for subject in self.subjects:
                # Count tutors teaching this subject
                available_tutors = [t for t in self.tutor_data if subject in t["subjects"]]
                tutors_count = len(available_tutors)

                # Calculate total capacity
                total_capacity = sum(t["weekly_capacity_hours"] for t in available_tutors)
                daily_capacity = total_capacity / 7  # Convert weekly to daily

                # Estimate used capacity based on sessions for this day/subject
                sessions_today = [
                    s for s in self.session_data
                    if s["scheduled_time"].date() == current_date.date()
                    and s["subject"] == subject
                ]
                used_capacity = sum(s["duration_minutes"] / 60 for s in sessions_today)

                utilization = (used_capacity / daily_capacity) if daily_capacity > 0 else 0.0

                snapshot = {
                    "subject": subject,
                    "date": current_date,
                    "total_capacity_hours": int(daily_capacity),
                    "used_capacity_hours": int(used_capacity),
                    "available_tutors_count": tutors_count,
                    "utilization_rate": round(min(utilization, 1.0), 2),
                }
                snapshots.append(snapshot)

            current_date += timedelta(days=1)

        self.capacity_snapshot_data = snapshots
        logger.info(f"Generated {len(snapshots)} capacity snapshot records")
        return snapshots

    async def batch_insert(self, session, model_class, data: List[Dict[str, Any]], batch_size: int = 1000):
        """Insert data in batches for performance (AC: 1, 2)"""
        if not data:
            return

        total_batches = (len(data) + batch_size - 1) // batch_size

        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            # Use bulk_insert_mappings for performance
            await session.run_sync(lambda sync_session: sync_session.bulk_insert_mappings(model_class, batch))

            logger.debug(f"Inserted batch {batch_num}/{total_batches} ({len(batch)} records)")

        await session.commit()

    async def generate_all_data(self):
        """Main entry point to generate all historical data"""
        start_time = datetime.now()
        logger.info("=== Starting Historical Data Generation ===")

        # Generate data in memory first (performance optimization)
        await self.generate_tutors()
        churned_tutor_dates = self.simulate_tutor_churn()
        await self.generate_enrollments()
        await self.generate_sessions(churned_tutor_dates)
        await self.generate_health_metrics()
        await self.generate_capacity_snapshots()

        # Insert to database using batch operations
        async with AsyncSessionLocal() as session:
            logger.info("Inserting tutors...")
            await self.batch_insert(session, Tutor, self.tutor_data)

            logger.info("Inserting enrollments...")
            await self.batch_insert(session, Enrollment, self.enrollment_data)

            logger.info("Inserting sessions...")
            await self.batch_insert(session, Session, self.session_data)

            logger.info("Inserting health metrics...")
            await self.batch_insert(session, HealthMetric, self.health_metric_data)

            logger.info("Inserting capacity snapshots...")
            await self.batch_insert(session, CapacitySnapshot, self.capacity_snapshot_data)

            # Initialize simulation state
            logger.info("Initializing simulation state...")
            sim_state = {
                "id": 1,
                "current_date": self.start_date,
                "speed_multiplier": 1,
                "is_running": False,
                "last_event": "Historical data generation completed",
            }
            await session.run_sync(lambda sync_session: sync_session.bulk_insert_mappings(SimulationState, [sim_state]))
            await session.commit()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=== Data Generation Complete ===")
        logger.info(f"Total time: {duration:.2f} seconds")
        logger.info(f"Tutors: {len(self.tutor_data)}")
        logger.info(f"Enrollments: {len(self.enrollment_data)}")
        logger.info(f"Sessions: {len(self.session_data)}")
        logger.info(f"Health Metrics: {len(self.health_metric_data)}")
        logger.info(f"Capacity Snapshots: {len(self.capacity_snapshot_data)}")

        return {
            "duration_seconds": duration,
            "tutors_count": len(self.tutor_data),
            "enrollments_count": len(self.enrollment_data),
            "sessions_count": len(self.session_data),
            "health_metrics_count": len(self.health_metric_data),
            "capacity_snapshots_count": len(self.capacity_snapshot_data),
        }

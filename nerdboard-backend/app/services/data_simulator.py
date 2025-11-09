"""
Real-Time Data Stream Simulator Service

Generates new data in real-time with configurable intervals, pause/resume/fast-forward controls.
Maintains realistic patterns from historical data generator.
"""

import asyncio
import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np

from app.database import AsyncSessionLocal
from app.models.enrollment import Enrollment
from app.models.tutor import Tutor
from app.models.session import Session
from app.models.simulation_state import SimulationState

# Import constants from data_generator for consistency (AC-5)
from app.services.data_generator import SUBJECTS, SUBJECT_WEIGHTS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulationStateManager:
    """Manages simulation state persistence (AC-6)"""

    def __init__(self):
        self.state: Optional[SimulationState] = None

    async def load_state(self) -> SimulationState:
        """Load simulation state from database (single-row table with id=1)"""
        async with AsyncSessionLocal() as session:
            # Query simulation_state where id=1 (single-row constraint)
            from sqlalchemy import select
            result = await session.execute(
                select(SimulationState).where(SimulationState.id == 1)
            )
            state = result.scalar_one_or_none()

            if state is None:
                # Initialize with defaults on first run
                state = SimulationState(
                    id=1,
                    current_date=datetime.now(),
                    speed_multiplier=1,
                    is_running=False,
                    last_event=None
                )
                session.add(state)
                await session.commit()
                await session.refresh(state)
                logger.info("Initialized simulation state with defaults")

            self.state = state
            return state

    async def save_state(
        self,
        current_date: Optional[datetime] = None,
        is_running: Optional[bool] = None,
        last_event: Optional[str] = None,
        speed_multiplier: Optional[int] = None
    ):
        """Save simulation state to database"""
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, update

            # Build update dict
            update_data = {}
            if current_date is not None:
                update_data["current_date"] = current_date
            if is_running is not None:
                update_data["is_running"] = is_running
            if last_event is not None:
                update_data["last_event"] = last_event
            if speed_multiplier is not None:
                update_data["speed_multiplier"] = speed_multiplier

            if update_data:
                stmt = (
                    update(SimulationState)
                    .where(SimulationState.id == 1)
                    .values(**update_data)
                )
                await session.execute(stmt)
                await session.commit()
                logger.debug(f"Saved simulation state: {update_data}")


class EventGenerator:
    """Generates enrollments, sessions, tutor status changes (AC-1, AC-5)"""

    def __init__(self, current_date: datetime):
        self.current_date = current_date
        self.subjects = SUBJECTS
        self.subject_weights = SUBJECT_WEIGHTS

    def _calculate_seasonal_multiplier(self, date: datetime) -> float:
        """
        Reuse seasonal pattern logic from data_generator.py (AC-5)
        +30% Sept, +20% Jan, -20% summer
        """
        month = date.month
        if month == 9:
            return 1.30  # September spike
        elif month == 1:
            return 1.20  # January spike
        elif month in [6, 7, 8]:
            return 0.80  # Summer dip
        else:
            return 1.0

    def _weighted_random_choice(self, items: List[str], weights: Dict[str, float]) -> str:
        """Select random item with weights (reused from data_generator.py)"""
        if weights and all(item in weights for item in items):
            return random.choices(items, weights=[weights[item] for item in items])[0]
        return random.choice(items)

    async def generate_enrollment_events(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate enrollment events using Poisson distribution (AC-1, AC-5)
        Uses subject weighting (30% SAT, 25% Math, etc.)
        """
        enrollments = []
        seasonal_mult = self._calculate_seasonal_multiplier(self.current_date)

        # Adjust count by seasonal multiplier
        adjusted_count = int(count * seasonal_mult)

        for _ in range(adjusted_count):
            student_id = uuid.uuid4()
            subject = self._weighted_random_choice(self.subjects, self.subject_weights)

            # Generate cohort_id with realistic pattern
            semester = "fall" if self.current_date.month >= 8 else "spring"
            year = self.current_date.year
            course_num = random.choice([101, 201, 301, "AP"])
            cohort_id = f"{year}-{semester}-{subject.lower().replace(' ', '-')}-{course_num}"

            # Engagement score: 0.4-1.0, weighted toward 0.6-0.8
            engagement = random.triangular(0.4, 1.0, 0.7)

            enrollment = {
                "student_id": student_id,
                "subject": subject,
                "cohort_id": cohort_id,
                "start_date": self.current_date,
                "engagement_score": round(engagement, 2),
            }
            enrollments.append(enrollment)

        logger.debug(f"Generated {len(enrollments)} enrollment events (seasonal mult: {seasonal_mult:.2f})")
        return enrollments

    async def generate_session_events(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate session events matching students to tutors (AC-1)
        """
        sessions = []

        # Query available tutors and enrollments
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            # Get random enrollments to match with tutors
            enrollments_result = await session.execute(
                select(Enrollment).limit(count * 2)  # Get extra to ensure matches
            )
            enrollments = list(enrollments_result.scalars().all())

            if not enrollments:
                logger.warning("No enrollments found for session generation")
                return []

            # Get all tutors
            tutors_result = await session.execute(select(Tutor))
            tutors = list(tutors_result.scalars().all())

            if not tutors:
                logger.warning("No tutors found for session generation")
                return []

            # Generate sessions
            for _ in range(count):
                enrollment = random.choice(enrollments)

                # Find tutors who teach this subject
                available_tutors = [
                    t for t in tutors
                    if enrollment.subject in t.subjects
                ]

                if not available_tutors:
                    continue

                tutor = random.choice(available_tutors)

                # Generate realistic time (peak hours: 4pm-9pm weekdays, 10am-6pm weekends)
                is_weekday = self.current_date.weekday() < 5
                if random.random() < 0.7:  # 70% peak hours
                    if is_weekday:
                        hour = random.randint(16, 21)
                    else:
                        hour = random.randint(10, 18)
                else:
                    hour = random.randint(8, 22)

                minute = random.choice([0, 15, 30, 45])
                scheduled_time = self.current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Duration: subject-appropriate
                if "SAT" in enrollment.subject or "Prep" in enrollment.subject:
                    duration = random.choice([60, 90, 120])
                else:
                    duration = random.choice([30, 45, 60, 90])

                session_data = {
                    "session_id": f"S{uuid.uuid4().hex[:6]}",
                    "subject": enrollment.subject,
                    "tutor_id": tutor.tutor_id,
                    "student_id": enrollment.student_id,
                    "scheduled_time": scheduled_time,
                    "duration_minutes": duration,
                }
                sessions.append(session_data)

        logger.debug(f"Generated {len(sessions)} session events")
        return sessions

    async def generate_tutor_status_changes(self, tutor_update_probability: float = 0.10) -> List[Dict[str, Any]]:
        """
        Generate tutor status changes (AC-1)
        Updates ~10% of tutors per event cycle
        """
        updates = []

        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            # Get all tutors
            result = await session.execute(select(Tutor))
            tutors = list(result.scalars().all())

            if not tutors:
                return []

            # Select random tutors to update
            num_updates = int(len(tutors) * tutor_update_probability)
            tutors_to_update = random.sample(tutors, min(num_updates, len(tutors)))

            for tutor in tutors_to_update:
                # Random availability change
                new_utilization = random.triangular(0.5, 0.9, 0.75)

                update = {
                    "tutor_id": tutor.tutor_id,
                    "utilization_rate": round(new_utilization, 2),
                }
                updates.append(update)

        logger.debug(f"Generated {len(updates)} tutor status changes")
        return updates


class DataSimulator:
    """Main simulation engine with pause/resume/fast-forward (AC-2, AC-3, AC-7)"""

    def __init__(
        self,
        event_interval_seconds: int = 300,  # 5 minutes default
        enrollments_per_cycle: int = 5,
        sessions_per_cycle: int = 10,
    ):
        self.event_interval_seconds = event_interval_seconds
        self.enrollments_per_cycle = enrollments_per_cycle
        self.sessions_per_cycle = sessions_per_cycle
        self.state_manager = SimulationStateManager()
        self.scheduler_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def start_simulation(self):
        """Start real-time simulation (AC-3)"""
        await self.state_manager.load_state()
        await self.state_manager.save_state(is_running=True)

        if self.scheduler_task is None or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self._event_generation_loop())

        logger.info("Simulation started")
        return {"status": "started", "current_time": datetime.now().isoformat()}

    async def pause_simulation(self):
        """Pause simulation (AC-3)"""
        await self.state_manager.save_state(is_running=False)
        logger.info("Simulation paused")
        return {"status": "paused", "current_time": datetime.now().isoformat()}

    async def get_status(self) -> Dict[str, Any]:
        """Get current simulation status (AC-4)"""
        state = await self.state_manager.load_state()
        return {
            "current_time": state.current_date.isoformat() if state.current_date else None,
            "is_running": state.is_running,
            "speed_multiplier": state.speed_multiplier or 1,
            "last_event_time": state.last_event if state.last_event else None,
        }

    async def advance_simulation(self, days: int) -> Dict[str, Any]:
        """
        Fast-forward simulation by N days (AC-7)
        Generates batch events for the time period
        """
        import time
        start_time = time.time()

        state = await self.state_manager.load_state()
        current_date = state.current_date or datetime.now()
        new_date = current_date + timedelta(days=days)

        # Calculate total events to generate
        cycles = days * (1440 // (self.event_interval_seconds // 60))  # cycles per day
        total_enrollments = cycles * self.enrollments_per_cycle
        total_sessions = cycles * self.sessions_per_cycle

        # Generate events in batches (1000 per batch for performance)
        batch_size = 1000
        enrollments_created = 0
        sessions_created = 0
        tutors_updated = 0

        # Generate enrollments
        for i in range(0, total_enrollments, batch_size):
            count = min(batch_size, total_enrollments - i)
            generator = EventGenerator(current_date + timedelta(days=i * days / total_enrollments))
            enrollments = await generator.generate_enrollment_events(count)

            if enrollments:
                await self._insert_enrollments(enrollments)
                enrollments_created += len(enrollments)

        # Generate sessions
        for i in range(0, total_sessions, batch_size):
            count = min(batch_size, total_sessions - i)
            generator = EventGenerator(current_date + timedelta(days=i * days / total_sessions))
            sessions = await generator.generate_session_events(count)

            if sessions:
                await self._insert_sessions(sessions)
                sessions_created += len(sessions)

        # Tutor updates
        generator = EventGenerator(new_date)
        tutor_updates = await generator.generate_tutor_status_changes()
        if tutor_updates:
            await self._update_tutors(tutor_updates)
            tutors_updated = len(tutor_updates)

        # Update simulation time
        await self.state_manager.save_state(
            current_date=new_date,
            last_event=f"fast-forward {days} days"
        )

        duration = time.time() - start_time
        logger.info(f"Fast-forwarded {days} days in {duration:.2f}s ({enrollments_created} enrollments, {sessions_created} sessions)")

        return {
            "days_advanced": days,
            "new_time": new_date.isoformat(),
            "events_generated": {
                "enrollments": enrollments_created,
                "sessions": sessions_created,
                "tutor_updates": tutors_updated
            },
            "duration_seconds": round(duration, 2)
        }

    async def _event_generation_loop(self):
        """Background event generation loop (AC-2)"""
        while not self._shutdown_event.is_set():
            try:
                state = await self.state_manager.load_state()

                if state.is_running:
                    await self._generate_event_cycle()

                await asyncio.sleep(self.event_interval_seconds)

            except asyncio.CancelledError:
                logger.info("Simulation scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in event generation loop: {e}", exc_info=True)
                await asyncio.sleep(self.event_interval_seconds)

    async def _generate_event_cycle(self):
        """Generate one cycle of events (AC-1)"""
        import time
        start_time = time.time()

        state = await self.state_manager.load_state()
        current_date = state.current_date or datetime.now()

        generator = EventGenerator(current_date)

        # Generate enrollments
        enrollments = await generator.generate_enrollment_events(self.enrollments_per_cycle)
        if enrollments:
            await self._insert_enrollments(enrollments)

        # Generate sessions
        sessions = await generator.generate_session_events(self.sessions_per_cycle)
        if sessions:
            await self._insert_sessions(sessions)
            # Trigger capacity updates for affected subjects (Story 1.4 integration)
            await self._update_capacity_for_sessions(sessions)

        # Tutor status changes
        tutor_updates = await generator.generate_tutor_status_changes()
        if tutor_updates:
            await self._update_tutors(tutor_updates)

        # Update state
        await self.state_manager.save_state(
            current_date=current_date + timedelta(seconds=self.event_interval_seconds),
            last_event=datetime.now().isoformat()
        )

        duration = time.time() - start_time
        logger.info(
            f"Event cycle complete: {len(enrollments)} enrollments, "
            f"{len(sessions)} sessions, {len(tutor_updates)} tutor updates ({duration:.3f}s)"
        )

    async def _insert_enrollments(self, enrollments: List[Dict[str, Any]]):
        """Batch insert enrollments"""
        async with AsyncSessionLocal() as session:
            await session.run_sync(
                lambda sync_session: sync_session.bulk_insert_mappings(Enrollment, enrollments)
            )
            await session.commit()

    async def _insert_sessions(self, sessions: List[Dict[str, Any]]):
        """Batch insert sessions"""
        async with AsyncSessionLocal() as session:
            await session.run_sync(
                lambda sync_session: sync_session.bulk_insert_mappings(Session, sessions)
            )
            await session.commit()

    async def _update_tutors(self, updates: List[Dict[str, Any]]):
        """Batch update tutors"""
        async with AsyncSessionLocal() as session:
            from sqlalchemy import update

            for upd in updates:
                stmt = (
                    update(Tutor)
                    .where(Tutor.tutor_id == upd["tutor_id"])
                    .values(utilization_rate=upd["utilization_rate"])
                )
                await session.execute(stmt)

            await session.commit()

    async def _update_capacity_for_sessions(self, sessions: List[Dict[str, Any]]):
        """
        Update capacity snapshots for subjects affected by session generation (Story 1.4).

        Args:
            sessions: List of session dicts with 'subject' key
        """
        try:
            # Import capacity calculator (lazy import to avoid circular dependency)
            from app.services.capacity_calculator import get_capacity_calculator

            # Get unique subjects from sessions
            subjects = set(session.get("subject") for session in sessions if session.get("subject"))

            if not subjects:
                return

            calculator = get_capacity_calculator()

            # Update capacity for each affected subject
            for subject in subjects:
                try:
                    for window in ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]:
                        metrics = await calculator.calculate_subject_capacity(subject, window)
                        await calculator.save_capacity_snapshot(subject, window, metrics)

                    logger.debug(f"Updated capacity for {subject} after session generation")
                except Exception as e:
                    logger.error(f"Error updating capacity for {subject}: {e}")

        except ImportError:
            # Capacity calculator not yet implemented (Story 1.4 not done)
            logger.debug("Capacity calculator not available, skipping capacity updates")
        except Exception as e:
            logger.error(f"Error in capacity update integration: {e}", exc_info=True)

    async def shutdown(self):
        """Graceful shutdown"""
        self._shutdown_event.set()
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Simulation shut down")


# Global simulator instance
_simulator: Optional[DataSimulator] = None


def get_simulator() -> DataSimulator:
    """Get or create global simulator instance"""
    global _simulator
    if _simulator is None:
        _simulator = DataSimulator()
    return _simulator

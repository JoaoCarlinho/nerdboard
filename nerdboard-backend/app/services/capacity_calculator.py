"""
Real-Time Subject Capacity Calculator

Calculates tutor utilization across multiple time windows (current_week, next_2_weeks,
next_4_weeks, next_8_weeks) with <50ms performance target.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.models.capacity_snapshot import CapacitySnapshot
from app.services.data_generator import SUBJECTS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_time_window_bounds(window_type: str) -> Tuple[datetime, datetime]:
    """
    Calculate Monday-Sunday week boundaries for time windows.

    Args:
        window_type: One of "current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"

    Returns:
        Tuple of (start_date, end_date) in UTC

    Raises:
        ValueError: If window_type is invalid
    """
    # Get today at midnight UTC
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Find current week's Monday (0=Monday, 6=Sunday)
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)

    if window_type == "current_week":
        start = current_monday
        end = current_monday + timedelta(days=7) - timedelta(seconds=1)
    elif window_type == "next_2_weeks":
        start = current_monday + timedelta(days=7)
        end = start + timedelta(days=14) - timedelta(seconds=1)
    elif window_type == "next_4_weeks":
        start = current_monday + timedelta(days=7)
        end = start + timedelta(days=28) - timedelta(seconds=1)
    elif window_type == "next_8_weeks":
        start = current_monday + timedelta(days=7)
        end = start + timedelta(days=56) - timedelta(seconds=1)
    else:
        raise ValueError(f"Invalid window type: {window_type}. Must be one of: current_week, next_2_weeks, next_4_weeks, next_8_weeks")

    return start, end


class CapacityCalculator:
    """
    Calculates subject capacity and utilization metrics.

    Implements AC-1, AC-2, AC-3, AC-4, AC-6, AC-7, AC-8:
    - Calculates total_tutor_hours, booked_hours, utilization_rate per subject
    - Tracks 4 time windows: current_week, next_2_weeks, next_4_weeks, next_8_weeks
    - Updates on session booking/completion with <50ms target
    - Stores snapshots in capacity_snapshots table
    - Determines status: normal (<85%), warning (85-95%), critical (>95%)
    """

    def __init__(self):
        self.time_windows = ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]

    def _determine_status(self, utilization_rate: float) -> str:
        """
        Determine capacity status based on utilization rate (AC-6).

        Args:
            utilization_rate: Float between 0 and 1

        Returns:
            Status string: "normal", "warning", or "critical"
        """
        if utilization_rate < 0.85:
            return "normal"
        elif utilization_rate < 0.95:
            return "warning"
        else:
            return "critical"

    async def calculate_subject_capacity(
        self,
        subject: str,
        window_type: str
    ) -> Dict[str, Any]:
        """
        Calculate capacity metrics for a subject in a time window (AC-1, AC-3, AC-7).

        Args:
            subject: Subject name (e.g., "Physics", "Math")
            window_type: Time window identifier

        Returns:
            Dict with:
                - total_hours: Sum of tutor availability for subject
                - booked_hours: Sum of booked session hours in window
                - utilization_rate: booked_hours / total_hours
                - status: "normal", "warning", or "critical"
                - window_start: ISO datetime
                - window_end: ISO datetime

        Raises:
            ValueError: If subject not in SUBJECTS or invalid window_type
        """
        import time
        start_time = time.time()

        # Validate subject
        if subject not in SUBJECTS:
            raise ValueError(f"Invalid subject: {subject}. Must be one of: {SUBJECTS}")

        # Get time window boundaries
        start_date, end_date = get_time_window_bounds(window_type)

        async with AsyncSessionLocal() as session:
            # Query total available hours for subject (AC-7)
            # Use PostgreSQL ANY() to check if subject is in subjects array
            tutor_query = text("""
                SELECT COALESCE(SUM(t.weekly_capacity_hours), 0) as total_hours
                FROM tutors t
                WHERE :subject = ANY(t.subjects)
            """)
            result = await session.execute(tutor_query, {"subject": subject})
            total_hours = result.scalar() or 0

            # Query booked hours for subject in time window (AC-1, AC-3)
            # Convert duration_minutes to hours
            session_query = text("""
                SELECT COALESCE(SUM(duration_minutes / 60.0), 0) as booked_hours
                FROM sessions
                WHERE subject = :subject
                AND scheduled_time BETWEEN :start_date AND :end_date
            """)
            result = await session.execute(session_query, {
                "subject": subject,
                "start_date": start_date,
                "end_date": end_date
            })
            booked_hours = result.scalar() or 0

            # Calculate utilization rate (AC-1)
            utilization_rate = (booked_hours / total_hours) if total_hours > 0 else 0

            # Determine status (AC-6)
            status = self._determine_status(utilization_rate)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Capacity calculation for {subject}/{window_type}: "
                f"{duration_ms:.2f}ms, utilization={utilization_rate:.2%}, status={status}"
            )

            return {
                "total_hours": round(total_hours, 2),
                "booked_hours": round(booked_hours, 2),
                "utilization_rate": round(utilization_rate, 4),
                "status": status,
                "window_start": start_date.isoformat(),
                "window_end": end_date.isoformat()
            }

    async def save_capacity_snapshot(
        self,
        subject: str,
        window_type: str,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Save capacity snapshot to database (AC-4).

        Args:
            subject: Subject name
            window_type: Time window identifier
            metrics: Capacity metrics dict from calculate_subject_capacity()
        """
        async with AsyncSessionLocal() as session:
            snapshot = CapacitySnapshot(
                subject=subject,
                time_window=window_type,
                total_hours=metrics["total_hours"],
                booked_hours=metrics["booked_hours"],
                utilization_rate=metrics["utilization_rate"],
                status=metrics["status"],
                snapshot_time=datetime.utcnow()
            )
            session.add(snapshot)
            await session.commit()

            logger.debug(
                f"Saved capacity snapshot: {subject}/{window_type}, "
                f"utilization={metrics['utilization_rate']:.2%}"
            )

    async def calculate_all_subjects_capacity(self) -> Dict[str, Any]:
        """
        Calculate capacity for all subjects across all time windows.

        Returns:
            Summary dict with:
                - subjects_calculated: Number of subjects processed
                - snapshots_created: Total snapshots saved
                - duration_ms: Total calculation time
        """
        import time
        start_time = time.time()

        snapshots_created = 0

        for subject in SUBJECTS:
            for window in self.time_windows:
                try:
                    metrics = await self.calculate_subject_capacity(subject, window)
                    await self.save_capacity_snapshot(subject, window, metrics)
                    snapshots_created += 1
                except Exception as e:
                    logger.error(f"Error calculating capacity for {subject}/{window}: {e}")

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Bulk capacity calculation complete: {len(SUBJECTS)} subjects, "
            f"{snapshots_created} snapshots, {duration_ms:.2f}ms"
        )

        return {
            "subjects_calculated": len(SUBJECTS),
            "snapshots_created": snapshots_created,
            "duration_ms": round(duration_ms, 2)
        }

    async def cleanup_old_snapshots(self, days: int = 90) -> int:
        """
        Delete snapshots older than specified days (AC-4 retention policy).

        Args:
            days: Number of days to retain

        Returns:
            Number of snapshots deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        async with AsyncSessionLocal() as session:
            delete_query = text("""
                DELETE FROM capacity_snapshots
                WHERE snapshot_time < :cutoff_date
            """)
            result = await session.execute(delete_query, {"cutoff_date": cutoff_date})
            await session.commit()

            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} capacity snapshots older than {days} days")

            return deleted_count


# Global calculator instance
_calculator: Optional[CapacityCalculator] = None


def get_capacity_calculator() -> CapacityCalculator:
    """Get or create global CapacityCalculator instance."""
    global _calculator
    if _calculator is None:
        _calculator = CapacityCalculator()
    return _calculator

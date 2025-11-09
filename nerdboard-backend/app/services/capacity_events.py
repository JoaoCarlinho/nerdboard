"""
Capacity Calculator Event Listeners

Auto-triggers capacity recalculation on session INSERT/UPDATE (AC-2, AC-8).
Ensures <50ms performance through async operations.
"""

import logging
import asyncio
from sqlalchemy import event
from app.models.session import Session
from app.services.capacity_calculator import get_capacity_calculator

logger = logging.getLogger(__name__)


def register_capacity_event_listeners():
    """
    Register SQLAlchemy event listeners for automatic capacity updates (AC-8).

    Call this function during app startup to enable automatic capacity recalculation
    when sessions are created or updated.
    """
    calculator = get_capacity_calculator()

    @event.listens_for(Session, 'after_insert')
    @event.listens_for(Session, 'after_update')
    def on_session_change(mapper, connection, target):
        """
        Trigger capacity recalculation when session is created/updated (AC-2, AC-8).

        This runs synchronously in the database transaction context, so we schedule
        the async capacity update to run in the background.
        """
        subject = target.subject

        # Schedule async capacity update
        # Note: In production, use a proper task queue (Celery, etc.)
        # For now, we use asyncio.create_task which works in async context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(update_capacity_for_subject(subject))
            else:
                # If no loop running, run in new loop (e.g., during tests)
                asyncio.run(update_capacity_for_subject(subject))
        except RuntimeError:
            # Handle case where event loop is not available
            logger.warning(
                f"Could not trigger capacity update for {subject}: "
                "No event loop available. Run in FastAPI context."
            )

    logger.info("Capacity event listeners registered")


async def update_capacity_for_subject(subject: str):
    """
    Async wrapper for capacity update after session change (AC-2).

    Recalculates capacity for all 4 time windows and saves snapshots.
    Target: <50ms total execution time.

    Args:
        subject: Subject name to recalculate
    """
    import time
    start_time = time.time()

    calculator = get_capacity_calculator()

    try:
        for window in ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]:
            metrics = await calculator.calculate_subject_capacity(subject, window)
            await calculator.save_capacity_snapshot(subject, window, metrics)

            # Log warnings/critical alerts (Task 10)
            if metrics["status"] == "warning":
                logger.warning(
                    f"Capacity WARNING: {subject}/{window} at {metrics['utilization_rate']:.1%} utilization"
                )
            elif metrics["status"] == "critical":
                logger.critical(
                    f"Capacity CRITICAL: {subject}/{window} at {metrics['utilization_rate']:.1%} utilization"
                )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Capacity updated for {subject}: {duration_ms:.2f}ms "
            f"(target: <50ms, {'PASS' if duration_ms < 50 else 'FAIL'})"
        )

    except Exception as e:
        logger.error(f"Error updating capacity for {subject}: {e}", exc_info=True)

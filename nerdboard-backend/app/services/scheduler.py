"""
APScheduler Configuration

Manages scheduled jobs for automated health score updates and other periodic tasks.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.health_score_calculator import get_health_calculator
from app.services.data_validator import get_data_validator
from app.services.prediction_service import get_prediction_service

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def update_customer_health_scores():
    """
    Hourly job to recalculate all customer health scores (AC-2).

    Runs every hour to update health scores for all active customers.
    Logs execution summary including customers processed and duration.
    """
    logger.info("Starting hourly health score update")

    try:
        calculator = get_health_calculator()
        summary = await calculator.calculate_all_customers_health()

        logger.info(
            f"Health scores updated: {summary['customers_processed']} customers "
            f"in {summary['duration_ms']:.2f}ms"
        )

        # Warn if performance target missed
        if summary['duration_ms'] > 5000:
            logger.warning(
                f"Health score update slow: {summary['duration_ms']:.2f}ms (target: <5000ms)"
            )

    except Exception as e:
        logger.error(f"Failed to update health scores: {e}", exc_info=True)


async def validate_data_quality():
    """
    Hourly job to validate data quality across all tables.

    Runs data validation checks and alerts on quality issues.
    """
    logger.info("Starting hourly data quality validation")

    try:
        validator = get_data_validator()
        summary = await validator.validate_all_tables()

        logger.info(
            f"Data quality validation complete: {summary['tables_validated']} tables, "
            f"avg score {summary['average_quality_score']:.1f}%"
        )

        # Warn if tables below threshold
        if summary['tables_below_threshold'] > 0:
            logger.warning(
                f"Quality ALERT: {summary['tables_below_threshold']} tables below 80% threshold"
            )

    except Exception as e:
        logger.error(f"Failed to validate data quality: {e}", exc_info=True)


async def generate_predictions():
    """
    Hourly job to generate capacity shortage predictions.

    Runs ML model predictions for all subjects across all horizons.
    """
    logger.info("Starting hourly prediction generation")

    try:
        prediction_service = get_prediction_service()
        summary = await prediction_service.generate_predictions_for_all_subjects()

        logger.info(
            f"Predictions generated: {summary['predictions_created']} predictions for "
            f"{summary['subjects_analyzed']} subjects in {summary['duration_seconds']:.1f}s"
        )

        # Warn if any critical predictions
        # Could query for is_critical=True predictions here

    except Exception as e:
        logger.error(f"Failed to generate predictions: {e}", exc_info=True)


def configure_scheduler():
    """
    Configure APScheduler with all scheduled jobs.

    Jobs:
        - Health score update: Every hour on the hour
        - Data quality validation: Every hour at :15
        - Prediction generation: Every hour at :30
    """
    # Hourly health score update
    scheduler.add_job(
        update_customer_health_scores,
        trigger=CronTrigger(hour='*'),  # Every hour at :00
        id='health_score_update',
        name='Update Customer Health Scores',
        replace_existing=True,
        coalesce=True,  # Combine missed runs into single execution
        max_instances=1  # Only one instance at a time
    )

    # Hourly data quality validation
    scheduler.add_job(
        validate_data_quality,
        trigger=CronTrigger(hour='*', minute=15),  # Every hour at :15
        id='data_quality_validation',
        name='Validate Data Quality',
        replace_existing=True,
        coalesce=True,
        max_instances=1
    )

    # Hourly prediction generation
    scheduler.add_job(
        generate_predictions,
        trigger=CronTrigger(hour='*', minute=30),  # Every hour at :30
        id='prediction_generation',
        name='Generate Capacity Shortage Predictions',
        replace_existing=True,
        coalesce=True,
        max_instances=1
    )

    logger.info("Scheduler configured with health scores, data quality, and prediction jobs")


def start_scheduler():
    """Start the APScheduler"""
    configure_scheduler()
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the APScheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")

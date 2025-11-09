"""
Customer Health Score Calculator

Calculates customer health scores (0-100) based on multiple engagement signals:
- First session success (40% weight)
- Session velocity (30% weight)
- IB call penalty (20% weight)
- Engagement score (10% weight)

Detects churn risk levels (low, medium, high) and provides cohort-level analytics.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.health_metric import HealthMetric
from app.services.data_generator import SUBJECTS

logger = logging.getLogger(__name__)


class HealthScoreCalculator:
    """Calculate customer health scores and detect churn risks"""

    def __init__(self):
        """Initialize health score calculator"""
        self.formula_weights = {
            "first_session_success": 0.40,
            "session_velocity": 0.30,
            "ib_penalty_inverse": 0.20,
            "engagement": 0.10
        }

    async def calculate_health_score(self, customer_id: str) -> float:
        """
        Calculate 0-100 health score for a single customer (AC-1).

        Formula:
            health_score = 0.4*first_session + 0.3*velocity + 0.2*(100-IB_penalty) + 0.1*engagement

        Args:
            customer_id: Customer UUID as string

        Returns:
            float: Health score 0-100

        Edge cases:
            - New customers with no sessions: first_session=0, velocity=0
            - Customers with no enrollments: engagement_score=0
            - Returns 0 if customer_id doesn't exist
        """
        try:
            # Get all components
            first_session = await self._get_first_session_success(customer_id)
            velocity = await self._calculate_session_velocity(customer_id)
            ib_penalty = await self._calculate_ib_penalty(customer_id)
            engagement = await self._get_engagement_score(customer_id)

            # Apply formula
            health_score = (
                self.formula_weights["first_session_success"] * first_session +
                self.formula_weights["session_velocity"] * velocity +
                self.formula_weights["ib_penalty_inverse"] * (100 - ib_penalty) +
                self.formula_weights["engagement"] * engagement
            )

            return round(health_score, 2)

        except Exception as e:
            logger.error(f"Error calculating health score for customer {customer_id}: {e}", exc_info=True)
            return 0.0

    async def _get_first_session_success(self, customer_id: str) -> float:
        """
        Determine if customer's first session was successful (0 or 100).

        Returns 100 if first session exists and is in past, 0 otherwise.

        Args:
            customer_id: Customer UUID as string

        Returns:
            float: 0 or 100
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT EXISTS(
                    SELECT 1 FROM sessions
                    WHERE CAST(student_id AS TEXT) = :customer_id
                    AND scheduled_time < NOW()
                    ORDER BY scheduled_time ASC
                    LIMIT 1
                ) as has_first_session
            """)
            result = await session.execute(query, {"customer_id": customer_id})
            has_first_session = result.scalar()

            return 100.0 if has_first_session else 0.0

    async def _calculate_session_velocity(self, customer_id: str) -> float:
        """
        Calculate sessions per week (last 30 days), normalized to 0-100.

        Formula:
            sessions_per_week = (session_count / 30) * 7
            normalized = min(sessions_per_week / 5.0 * 100, 100)

        Assumes 5 sessions/week is maximum healthy velocity.

        Args:
            customer_id: Customer UUID as string

        Returns:
            float: 0-100
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT COUNT(*) as session_count
                FROM sessions
                WHERE CAST(student_id AS TEXT) = :customer_id
                AND scheduled_time >= NOW() - INTERVAL '30 days'
                AND scheduled_time <= NOW()
            """)
            result = await session.execute(query, {"customer_id": customer_id})
            session_count = result.scalar() or 0

            # Calculate sessions per week
            sessions_per_week = (session_count / 30.0) * 7.0

            # Normalize to 0-100 scale (5 sessions/week = 100)
            normalized = min(sessions_per_week / 5.0 * 100, 100)

            return round(normalized, 2)

    async def _calculate_ib_penalty(self, customer_id: str) -> float:
        """
        Calculate IB call penalty (0, 20, or 50) based on recent support tickets.

        Logic:
            - 0 calls: penalty = 0
            - 1 call: penalty = 20
            - 2+ calls: penalty = 50

        Args:
            customer_id: Customer UUID as string

        Returns:
            float: 0, 20, or 50
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT COALESCE(SUM(support_ticket_count), 0) as total_ib_calls
                FROM health_metrics
                WHERE customer_id = :customer_id
                AND date >= NOW() - INTERVAL '14 days'
            """)
            result = await session.execute(query, {"customer_id": customer_id})
            total_ib_calls = result.scalar() or 0

            if total_ib_calls == 0:
                return 0.0
            elif total_ib_calls == 1:
                return 20.0
            else:
                return 50.0

    async def _get_engagement_score(self, customer_id: str) -> float:
        """
        Get latest engagement score from enrollments, scaled to 0-100.

        Args:
            customer_id: Customer UUID as string

        Returns:
            float: 0-100
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT engagement_score
                FROM enrollments
                WHERE CAST(student_id AS TEXT) = :customer_id
                ORDER BY start_date DESC
                LIMIT 1
            """)
            result = await session.execute(query, {"customer_id": customer_id})
            engagement_score = result.scalar()

            if engagement_score is None:
                return 0.0

            # Scale from 0-1 to 0-100
            return round(engagement_score * 100, 2)

    async def detect_churn_risk(self, customer_id: str) -> str:
        """
        Determine churn risk level: "low", "medium", "high" (AC-3).

        Logic:
            - High: ≥2 IB calls in 14 days OR health_score < 40
            - Medium: 1 IB call in 14 days OR health_score 40-60
            - Low: 0 IB calls AND health_score > 60

        Args:
            customer_id: Customer UUID as string

        Returns:
            str: "low", "medium", or "high"
        """
        try:
            # Get IB calls
            ib_penalty = await self._calculate_ib_penalty(customer_id)
            ib_calls = 0 if ib_penalty == 0 else (1 if ib_penalty == 20 else 2)

            # Get health score
            health_score = await self.calculate_health_score(customer_id)

            # Determine risk level
            if ib_calls >= 2 or health_score < 40:
                return "high"
            elif ib_calls == 1 or health_score < 60:
                return "medium"
            else:
                return "low"

        except Exception as e:
            logger.error(f"Error detecting churn risk for customer {customer_id}: {e}", exc_info=True)
            return "medium"  # Default to medium risk on error

    async def calculate_all_customers_health(self) -> Dict[str, Any]:
        """
        Batch calculate health scores for all active customers (AC-2, AC-7).

        Active customers: those with enrollments in last 90 days.
        Performance target: <5 seconds for 500 customers.

        Returns:
            dict: {
                "customers_processed": int,
                "health_scores_updated": int,
                "duration_ms": float,
                "timestamp": str
            }
        """
        import time
        start_time = time.time()

        try:
            # Get all active customer IDs
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT DISTINCT CAST(student_id AS TEXT) as customer_id
                    FROM enrollments
                    WHERE start_date >= NOW() - INTERVAL '90 days'
                """)
                result = await session.execute(query)
                customer_ids = [row.customer_id for row in result.fetchall()]

            logger.info(f"Starting health score calculation for {len(customer_ids)} customers")

            # Calculate health scores in parallel
            tasks = [self._calculate_and_save_health(customer_id) for customer_id in customer_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful updates
            successful_updates = sum(1 for r in results if r is True)
            failed_updates = sum(1 for r in results if isinstance(r, Exception))

            duration_ms = (time.time() - start_time) * 1000

            summary = {
                "customers_processed": len(customer_ids),
                "health_scores_updated": successful_updates,
                "failed_updates": failed_updates,
                "duration_ms": round(duration_ms, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Health score calculation complete: {summary}")

            # Warn if performance target missed
            if duration_ms > 5000:
                logger.warning(f"Health score batch calculation slow: {duration_ms:.2f}ms (target: <5000ms)")

            return summary

        except Exception as e:
            logger.error(f"Error in batch health score calculation: {e}", exc_info=True)
            duration_ms = (time.time() - start_time) * 1000
            return {
                "customers_processed": 0,
                "health_scores_updated": 0,
                "failed_updates": 0,
                "duration_ms": round(duration_ms, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def _calculate_and_save_health(self, customer_id: str) -> bool:
        """
        Calculate health score for customer and save to database.

        Args:
            customer_id: Customer UUID as string

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate health score and churn risk
            health_score = await self.calculate_health_score(customer_id)
            churn_risk = await self.detect_churn_risk(customer_id)

            # Get component metrics for storage
            engagement = await self._get_engagement_score(customer_id)

            # Save to database
            health_data = {
                "health_score": health_score,
                "engagement_level": int(engagement),  # Store as integer 0-100
                "churn_risk_level": churn_risk
            }

            await self.save_health_metric(customer_id, health_data)

            # Log high churn risk
            if churn_risk == "high":
                ib_calls = await self._calculate_ib_penalty(customer_id)
                logger.warning(
                    f"Churn risk HIGH: customer {customer_id}, "
                    f"score {health_score}, IB penalty {ib_calls}"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to calculate/save health for customer {customer_id}: {e}")
            return False

    async def save_health_metric(self, customer_id: str, health_data: Dict[str, Any]) -> None:
        """
        Persist health metric to database (AC-4).

        Updates existing record if one exists for today, otherwise inserts new record.

        Args:
            customer_id: Customer UUID as string
            health_data: Dict with health_score, engagement_level, etc.
        """
        async with AsyncSessionLocal() as session:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # Check if record exists for today
            query = text("""
                SELECT id FROM health_metrics
                WHERE customer_id = :customer_id
                AND date = :today
            """)
            result = await session.execute(query, {"customer_id": customer_id, "today": today})
            existing_id = result.scalar()

            if existing_id:
                # Update existing record
                update_query = text("""
                    UPDATE health_metrics
                    SET health_score = :health_score,
                        engagement_level = :engagement_level,
                        updated_at = NOW()
                    WHERE id = :id
                """)
                await session.execute(update_query, {
                    "id": existing_id,
                    "health_score": health_data["health_score"],
                    "engagement_level": health_data.get("engagement_level", 0)
                })
            else:
                # Insert new record
                health_metric = HealthMetric(
                    customer_id=customer_id,
                    date=today,
                    health_score=health_data["health_score"],
                    engagement_level=health_data.get("engagement_level", 0),
                    support_ticket_count=health_data.get("support_ticket_count", 0)
                )
                session.add(health_metric)

            await session.commit()

    async def get_dashboard_health_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated health metrics for dashboard overview (AC-8).

        Returns system-wide health aggregates from last 24 hours.

        Returns:
            dict: Dashboard health metrics
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT
                    COUNT(DISTINCT customer_id) as total_customers,
                    AVG(health_score) as avg_health_score,
                    SUM(CASE WHEN health_score < 40 THEN 1 ELSE 0 END) as high_risk_count,
                    SUM(CASE WHEN health_score BETWEEN 40 AND 60 THEN 1 ELSE 0 END) as medium_risk_count,
                    SUM(CASE WHEN health_score > 60 THEN 1 ELSE 0 END) as low_risk_count
                FROM health_metrics
                WHERE date >= NOW() - INTERVAL '1 day'
            """)
            result = await session.execute(query)
            row = result.fetchone()

            return {
                "total_customers": row.total_customers or 0,
                "avg_health_score": round(row.avg_health_score, 2) if row.avg_health_score else 0.0,
                "health_distribution": {
                    "high": row.low_risk_count or 0,  # High health (>60)
                    "medium": row.medium_risk_count or 0,  # Medium health (40-60)
                    "low": row.high_risk_count or 0  # Low health (<40)
                },
                "churn_risk_counts": {
                    "high": row.high_risk_count or 0,  # High churn risk (<40)
                    "medium": row.medium_risk_count or 0,  # Medium churn risk (40-60)
                    "low": row.low_risk_count or 0  # Low churn risk (>60)
                }
            }

    async def calculate_cohort_health_aggregates(self, cohort_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculate health aggregates per cohort for segmentation analysis (AC-5).

        Args:
            cohort_id: Optional specific cohort to analyze, None for all cohorts

        Returns:
            list: Cohort health aggregates
        """
        async with AsyncSessionLocal() as session:
            if cohort_id:
                query = text("""
                    SELECT
                        e.cohort_id,
                        COUNT(DISTINCT hm.customer_id) as customer_count,
                        AVG(hm.health_score) as avg_health_score,
                        SUM(CASE WHEN hm.health_score < 40 THEN 1 ELSE 0 END) as churn_risk_high
                    FROM health_metrics hm
                    JOIN enrollments e ON hm.customer_id = CAST(e.student_id AS TEXT)
                    WHERE e.cohort_id = :cohort_id
                    AND hm.date >= NOW() - INTERVAL '1 day'
                    GROUP BY e.cohort_id
                """)
                result = await session.execute(query, {"cohort_id": cohort_id})
            else:
                query = text("""
                    SELECT
                        e.cohort_id,
                        COUNT(DISTINCT hm.customer_id) as customer_count,
                        AVG(hm.health_score) as avg_health_score,
                        SUM(CASE WHEN hm.health_score < 40 THEN 1 ELSE 0 END) as churn_risk_high
                    FROM health_metrics hm
                    JOIN enrollments e ON hm.customer_id = CAST(e.student_id AS TEXT)
                    WHERE hm.date >= NOW() - INTERVAL '1 day'
                    GROUP BY e.cohort_id
                    ORDER BY customer_count DESC
                """)
                result = await session.execute(query)

            cohorts = []
            for row in result.fetchall():
                cohorts.append({
                    "cohort_id": row.cohort_id,
                    "customer_count": row.customer_count,
                    "avg_health_score": round(row.avg_health_score, 2) if row.avg_health_score else 0.0,
                    "churn_risk_high": row.churn_risk_high or 0
                })

            return cohorts


# Singleton instance
_health_calculator_instance: Optional[HealthScoreCalculator] = None


def get_health_calculator() -> HealthScoreCalculator:
    """Get singleton instance of HealthScoreCalculator"""
    global _health_calculator_instance
    if _health_calculator_instance is None:
        _health_calculator_instance = HealthScoreCalculator()
    return _health_calculator_instance

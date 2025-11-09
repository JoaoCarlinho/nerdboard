"""
Feature Engineering Pipeline

Extracts time-series features from raw data for ML model input.
Generates rolling averages, trends, velocity metrics, and seasonality features.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature extraction service for capacity shortage prediction.

    Generates time-series features:
    - Rolling averages (7-day, 14-day, 30-day)
    - Enrollment velocity
    - Tutor churn rate
    - Session completion rate
    - Utilization trends
    - Seasonal factors
    """

    def __init__(self):
        self.feature_windows = {
            "short": 7,   # 7-day rolling window
            "medium": 14,  # 14-day rolling window
            "long": 30     # 30-day rolling window
        }

    async def extract_features_for_subject(
        self,
        subject: str,
        reference_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract all features for a specific subject at a reference date.

        Args:
            subject: Subject name (e.g., "Physics", "SAT Prep")
            reference_date: Date to extract features for (default: now)

        Returns:
            Dictionary of features with values
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        logger.info(f"Extracting features for {subject} at {reference_date.date()}")

        async with AsyncSessionLocal() as session:
            # Extract all feature components
            enrollment_features = await self._get_enrollment_features(session, subject, reference_date)
            tutor_features = await self._get_tutor_features(session, subject, reference_date)
            session_features = await self._get_session_features(session, subject, reference_date)
            utilization_features = await self._get_utilization_features(session, subject, reference_date)
            seasonal_features = await self._get_seasonal_features(session, subject, reference_date)

            # Combine all features
            features = {
                "subject": subject,
                "reference_date": reference_date.isoformat(),
                **enrollment_features,
                **tutor_features,
                **session_features,
                **utilization_features,
                **seasonal_features
            }

            # Store features in database
            await self._store_features(session, subject, reference_date, features)

        return features

    async def extract_features_for_all_subjects(
        self,
        reference_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract features for all subjects.

        Args:
            reference_date: Date to extract features for (default: now)

        Returns:
            List of feature dictionaries, one per subject
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            # Get list of all subjects
            query = text("SELECT DISTINCT subject FROM enrollments ORDER BY subject")
            result = await session.execute(query)
            subjects = [row.subject for row in result.fetchall()]

        logger.info(f"Extracting features for {len(subjects)} subjects")

        all_features = []
        for subject in subjects:
            features = await self.extract_features_for_subject(subject, reference_date)
            all_features.append(features)

        return all_features

    async def _get_enrollment_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime
    ) -> Dict[str, float]:
        """Extract enrollment-related features"""

        # Get enrollment counts for different windows
        features = {}

        for window_name, days in self.feature_windows.items():
            start_date = reference_date - timedelta(days=days)

            query = text("""
                SELECT COUNT(*) as enrollment_count
                FROM enrollments
                WHERE subject = :subject
                AND start_date >= :start_date
                AND start_date <= :reference_date
            """)
            result = await session.execute(query, {
                "subject": subject,
                "start_date": start_date,
                "reference_date": reference_date
            })
            row = result.fetchone()
            count = row.enrollment_count if row else 0

            features[f"enrollment_count_{window_name}"] = float(count)
            features[f"enrollment_rate_{window_name}"] = float(count) / days  # per day

        # Calculate enrollment velocity (week-over-week change)
        this_week_start = reference_date - timedelta(days=7)
        last_week_start = reference_date - timedelta(days=14)

        query_this_week = text("""
            SELECT COUNT(*) as count
            FROM enrollments
            WHERE subject = :subject
            AND start_date >= :start_date
            AND start_date <= :end_date
        """)

        # This week
        result = await session.execute(query_this_week, {
            "subject": subject,
            "start_date": this_week_start,
            "end_date": reference_date
        })
        this_week_count = result.fetchone().count

        # Last week
        result = await session.execute(query_this_week, {
            "subject": subject,
            "start_date": last_week_start,
            "end_date": this_week_start
        })
        last_week_count = result.fetchone().count

        # Velocity calculation
        if last_week_count > 0:
            enrollment_velocity = (this_week_count - last_week_count) / last_week_count
        else:
            enrollment_velocity = 0.0 if this_week_count == 0 else 1.0

        features["enrollment_velocity"] = float(enrollment_velocity)
        features["enrollment_this_week"] = float(this_week_count)
        features["enrollment_last_week"] = float(last_week_count)

        return features

    async def _get_tutor_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime
    ) -> Dict[str, float]:
        """Extract tutor-related features"""

        # Current tutor count and capacity
        query = text("""
            SELECT
                COUNT(*) as tutor_count,
                COALESCE(SUM(weekly_capacity_hours), 0) as total_capacity,
                COALESCE(AVG(utilization_rate), 0) as avg_utilization
            FROM tutors
            WHERE :subject = ANY(subjects)
        """)
        result = await session.execute(query, {"subject": subject})
        row = result.fetchone()

        features = {
            "tutor_count": float(row.tutor_count if row else 0),
            "total_capacity_hours": float(row.total_capacity if row else 0),
            "avg_tutor_utilization": float(row.avg_utilization if row else 0)
        }

        # Tutor churn rate (tutors who left in last 30 days)
        # Note: In MVP, we don't track tutor departures, so this is placeholder
        # In production, would query tutor status changes
        features["tutor_churn_rate_30d"] = 0.0  # Placeholder

        return features

    async def _get_session_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime
    ) -> Dict[str, float]:
        """Extract session-related features"""

        features = {}

        for window_name, days in self.feature_windows.items():
            start_date = reference_date - timedelta(days=days)

            # Session counts
            query = text("""
                SELECT
                    COUNT(*) as session_count,
                    COALESCE(SUM(duration_minutes), 0) as total_minutes
                FROM sessions
                WHERE subject = :subject
                AND scheduled_time >= :start_date
                AND scheduled_time <= :reference_date
            """)
            result = await session.execute(query, {
                "subject": subject,
                "start_date": start_date,
                "reference_date": reference_date
            })
            row = result.fetchone()

            session_count = row.session_count if row else 0
            total_hours = (row.total_minutes if row else 0) / 60.0

            features[f"session_count_{window_name}"] = float(session_count)
            features[f"session_hours_{window_name}"] = float(total_hours)
            features[f"session_rate_{window_name}"] = float(session_count) / days

        # Session completion rate (placeholder - would need completion status)
        features["session_completion_rate"] = 0.95  # Placeholder: assume 95%

        return features

    async def _get_utilization_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime
    ) -> Dict[str, float]:
        """Extract utilization trend features"""

        # Get weekly utilization for last 4 weeks
        weekly_utils = []

        for week in range(4):
            week_end = reference_date - timedelta(days=week * 7)
            week_start = week_end - timedelta(days=7)

            # Total capacity
            query_capacity = text("""
                SELECT COALESCE(SUM(weekly_capacity_hours), 0) as capacity
                FROM tutors
                WHERE :subject = ANY(subjects)
            """)
            result = await session.execute(query_capacity, {"subject": subject})
            capacity = result.fetchone().capacity

            # Booked hours
            query_booked = text("""
                SELECT COALESCE(SUM(duration_minutes), 0) / 60.0 as booked
                FROM sessions
                WHERE subject = :subject
                AND scheduled_time >= :start_date
                AND scheduled_time < :end_date
            """)
            result = await session.execute(query_booked, {
                "subject": subject,
                "start_date": week_start,
                "end_date": week_end
            })
            booked = result.fetchone().booked

            utilization = (booked / capacity * 100) if capacity > 0 else 0.0
            weekly_utils.append(utilization)

        # Calculate trend (linear regression slope)
        if len(weekly_utils) >= 2:
            weeks_array = np.array(range(len(weekly_utils)))
            utils_array = np.array(weekly_utils)

            # Simple linear regression
            slope, _ = np.polyfit(weeks_array, utils_array, 1)
            utilization_trend = float(slope)
        else:
            utilization_trend = 0.0

        features = {
            "utilization_current_week": float(weekly_utils[0]) if weekly_utils else 0.0,
            "utilization_last_week": float(weekly_utils[1]) if len(weekly_utils) > 1 else 0.0,
            "utilization_2_weeks_ago": float(weekly_utils[2]) if len(weekly_utils) > 2 else 0.0,
            "utilization_3_weeks_ago": float(weekly_utils[3]) if len(weekly_utils) > 3 else 0.0,
            "utilization_trend": utilization_trend,
            "utilization_avg_4weeks": float(np.mean(weekly_utils)) if weekly_utils else 0.0
        }

        return features

    async def _get_seasonal_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime
    ) -> Dict[str, float]:
        """Extract seasonal pattern features"""

        current_month = reference_date.month

        # Calculate yearly average enrollment for this subject
        query_yearly = text("""
            SELECT COUNT(*) / 12.0 as monthly_avg
            FROM enrollments
            WHERE subject = :subject
            AND start_date >= :year_ago
            AND start_date <= :reference_date
        """)
        result = await session.execute(query_yearly, {
            "subject": subject,
            "year_ago": reference_date - timedelta(days=365),
            "reference_date": reference_date
        })
        yearly_avg = result.fetchone().monthly_avg if result.fetchone() else 0

        # Get current month enrollment
        month_start = reference_date.replace(day=1)
        query_current_month = text("""
            SELECT COUNT(*) as count
            FROM enrollments
            WHERE subject = :subject
            AND start_date >= :month_start
            AND start_date <= :reference_date
        """)
        result = await session.execute(query_current_month, {
            "subject": subject,
            "month_start": month_start,
            "reference_date": reference_date
        })
        current_month_count = result.fetchone().count

        # Seasonal factor: current month vs yearly average
        seasonal_factor = (current_month_count / yearly_avg) if yearly_avg > 0 else 1.0

        # Known seasonal patterns (domain knowledge)
        # Sept-Oct: back-to-school spike (+30%)
        # June-Aug: summer dip (-20%)
        known_seasonal_multiplier = 1.0
        if current_month in [9, 10]:  # September, October
            known_seasonal_multiplier = 1.3
        elif current_month in [6, 7, 8]:  # June, July, August
            known_seasonal_multiplier = 0.8

        features = {
            "seasonal_factor": float(seasonal_factor),
            "month_of_year": float(current_month),
            "known_seasonal_multiplier": float(known_seasonal_multiplier),
            "is_back_to_school_season": 1.0 if current_month in [9, 10] else 0.0,
            "is_summer_season": 1.0 if current_month in [6, 7, 8] else 0.0
        }

        return features

    async def _store_features(
        self,
        session: AsyncSession,
        subject: str,
        reference_date: datetime,
        features: Dict[str, Any]
    ):
        """Store extracted features in prediction_features table"""

        # Remove non-numeric fields for JSON storage
        features_json = {k: v for k, v in features.items()
                        if k not in ["subject", "reference_date"]}

        # Upsert into prediction_features table
        query = text("""
            INSERT INTO prediction_features (subject, reference_date, features_json, created_at)
            VALUES (:subject, :reference_date, :features_json, :created_at)
            ON CONFLICT (subject, reference_date)
            DO UPDATE SET
                features_json = EXCLUDED.features_json,
                created_at = EXCLUDED.created_at
        """)

        await session.execute(query, {
            "subject": subject,
            "reference_date": reference_date,
            "features_json": features_json,
            "created_at": datetime.utcnow()
        })
        await session.commit()

        logger.info(f"Stored {len(features_json)} features for {subject}")


# Singleton instance
_feature_engineer_instance = None


def get_feature_engineer() -> FeatureEngineer:
    """Get singleton FeatureEngineer instance"""
    global _feature_engineer_instance
    if _feature_engineer_instance is None:
        _feature_engineer_instance = FeatureEngineer()
    return _feature_engineer_instance

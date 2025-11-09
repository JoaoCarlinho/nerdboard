"""
Confidence Score Calculator

Calculates confidence scores for predictions based on multiple factors:
- Model certainty (probability distance from 0.5)
- Data quality
- Pattern strength (trend R²)
- Historical accuracy
"""
import logging
from typing import Dict, Any, Optional
import numpy as np
from sqlalchemy import text

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """
    Calculates confidence scores (0-100%) for shortage predictions.

    Formula: 40% model_certainty + 25% data_quality + 20% pattern_strength + 15% historical_accuracy
    """

    def __init__(self):
        self.weights = {
            "model_certainty": 0.40,
            "data_quality": 0.25,
            "pattern_strength": 0.20,
            "historical_accuracy": 0.15
        }

        # Confidence thresholds
        self.low_confidence_threshold = 60.0
        self.high_confidence_threshold = 80.0

    async def calculate_confidence(
        self,
        subject: str,
        shortage_probability: float,
        features: Dict[str, float],
        data_quality_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate confidence score for a prediction.

        Args:
            subject: Subject name
            shortage_probability: Model's shortage probability (0-1)
            features: Feature dictionary used for prediction
            data_quality_score: Optional pre-calculated data quality (0-100)

        Returns:
            Dictionary with confidence score and breakdown
        """
        # Calculate individual components
        model_certainty = self._calculate_model_certainty(shortage_probability)
        pattern_strength = self._calculate_pattern_strength(features)
        historical_accuracy = await self._calculate_historical_accuracy(subject)

        if data_quality_score is None:
            data_quality_score = await self._get_data_quality_score(subject)

        # Weighted combination
        confidence_score = (
            self.weights["model_certainty"] * model_certainty +
            self.weights["data_quality"] * data_quality_score +
            self.weights["pattern_strength"] * pattern_strength +
            self.weights["historical_accuracy"] * historical_accuracy
        )

        # Determine confidence level
        if confidence_score >= self.high_confidence_threshold:
            confidence_level = "high"
        elif confidence_score >= self.low_confidence_threshold:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        return {
            "confidence_score": round(confidence_score, 2),
            "confidence_level": confidence_level,
            "breakdown": {
                "model_certainty": round(model_certainty, 2),
                "data_quality": round(data_quality_score, 2),
                "pattern_strength": round(pattern_strength, 2),
                "historical_accuracy": round(historical_accuracy, 2)
            },
            "is_uncertain": confidence_score < self.low_confidence_threshold
        }

    def _calculate_model_certainty(self, probability: float) -> float:
        """
        Calculate model certainty from probability.

        Model is most certain when probability is close to 0 or 1,
        least certain when close to 0.5.

        Args:
            probability: Shortage probability (0-1)

        Returns:
            Certainty score (0-100)
        """
        # Distance from 0.5 (uncertainty point)
        distance_from_midpoint = abs(probability - 0.5)

        # Convert to 0-100 scale
        # distance_from_midpoint ranges from 0 (uncertain) to 0.5 (certain)
        certainty = (distance_from_midpoint / 0.5) * 100

        return certainty

    def _calculate_pattern_strength(self, features: Dict[str, float]) -> float:
        """
        Calculate pattern strength based on trend consistency.

        Strong patterns have clear trends in utilization and enrollment.

        Args:
            features: Feature dictionary

        Returns:
            Pattern strength score (0-100)
        """
        # Get utilization trend strength
        utilization_trend = abs(features.get("utilization_trend", 0))

        # Get enrollment velocity magnitude
        enrollment_velocity = abs(features.get("enrollment_velocity", 0))

        # Calculate R² equivalent for trend strength
        # Strong trends have high absolute values
        # Normalize to 0-100 scale

        # Utilization trend: map [0, 10] to [0, 100]
        # 10% trend per week is very strong
        util_strength = min(abs(utilization_trend) * 10, 100)

        # Enrollment velocity: map [0, 0.5] to [0, 100]
        # 50% velocity change is very strong
        enroll_strength = min(abs(enrollment_velocity) * 200, 100)

        # Average of both
        pattern_strength = (util_strength + enroll_strength) / 2

        return pattern_strength

    async def _calculate_historical_accuracy(self, subject: str) -> float:
        """
        Calculate historical accuracy of predictions for this subject.

        In MVP, this is a placeholder. In production, would analyze
        past predictions vs actual outcomes.

        Args:
            subject: Subject name

        Returns:
            Historical accuracy score (0-100)
        """
        # Placeholder: Return baseline accuracy
        # In production, would query past predictions and outcomes

        async with AsyncSessionLocal() as session:
            # Check if we have historical predictions for this subject
            query = text("""
                SELECT COUNT(*) as count
                FROM predictions
                WHERE subject = :subject
            """)
            result = await session.execute(query, {"subject": subject})
            count = result.fetchone().count

            # If we have history, use moderate confidence
            # If new subject, use lower confidence
            if count > 10:
                return 75.0  # Moderate historical confidence
            elif count > 0:
                return 60.0  # Some history
            else:
                return 50.0  # No history, neutral

    async def _get_data_quality_score(self, subject: str) -> float:
        """
        Get data quality score for this subject.

        Retrieves from data_quality_log or returns default.

        Args:
            subject: Subject name

        Returns:
            Data quality score (0-100)
        """
        async with AsyncSessionLocal() as session:
            # Get latest quality score from relevant tables
            query = text("""
                SELECT AVG(quality_score) as avg_quality
                FROM (
                    SELECT quality_score
                    FROM data_quality_log
                    WHERE table_name IN ('enrollments', 'sessions', 'tutors')
                    AND validation_time >= NOW() - INTERVAL '24 hours'
                    ORDER BY validation_time DESC
                    LIMIT 10
                ) recent_quality
            """)
            result = await session.execute(query)
            row = result.fetchone()

            if row and row.avg_quality:
                return float(row.avg_quality)
            else:
                # Default to high quality if no quality data
                return 90.0

    def get_confidence_tag(self, confidence_score: float) -> str:
        """
        Get human-readable confidence tag.

        Args:
            confidence_score: Confidence score (0-100)

        Returns:
            Tag string ("uncertain", "moderate", "high")
        """
        if confidence_score < self.low_confidence_threshold:
            return "uncertain"
        elif confidence_score < self.high_confidence_threshold:
            return "moderate"
        else:
            return "high"


# Singleton instance
_confidence_calculator_instance = None


def get_confidence_calculator() -> ConfidenceCalculator:
    """Get singleton ConfidenceCalculator instance"""
    global _confidence_calculator_instance
    if _confidence_calculator_instance is None:
        _confidence_calculator_instance = ConfidenceCalculator()
    return _confidence_calculator_instance

"""
Prediction Service

Orchestrates the complete prediction pipeline:
- Feature extraction
- ML model prediction
- Confidence scoring
- SHAP explainability
- Natural language explanation generation
- Prioritization
- Storage
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.services.feature_engineer import get_feature_engineer
from app.ml.shortage_predictor import get_shortage_predictor
from app.ml.confidence_calculator import get_confidence_calculator
from app.ml.explainability import create_explainability_engine
from app.ml.explanation_generator import get_explanation_generator

logger = logging.getLogger(__name__)


class PredictionService:
    """
    End-to-end prediction service.

    Generates capacity shortage predictions with full explainability.
    """

    def __init__(self):
        self.horizons = ["2week", "4week", "6week", "8week"]
        self.probability_threshold = 0.10  # Only create predictions if >10% probability change

    async def generate_prediction_for_subject(
        self,
        subject: str,
        horizon: str = "2week"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate complete prediction for a subject.

        Args:
            subject: Subject name
            horizon: Prediction horizon (2week, 4week, 6week, 8week)

        Returns:
            Complete prediction with explanation, or None if skipped
        """
        logger.info(f"Generating {horizon} prediction for {subject}")

        try:
            # 1. Extract features
            engineer = get_feature_engineer()
            features = await engineer.extract_features_for_subject(subject)

            # 2. Run ML model prediction
            predictor = get_shortage_predictor()
            prediction = predictor.predict_shortage(features, horizon)

            # 3. Calculate confidence score
            confidence_calc = get_confidence_calculator()
            confidence = await confidence_calc.calculate_confidence(
                subject,
                prediction["shortage_probability"],
                features
            )

            # 4. Generate SHAP explanation
            explainer = create_explainability_engine(
                predictor.model,
                predictor.feature_columns
            )
            top_features = explainer.explain_prediction(features, top_n=5)

            # 5. Generate natural language explanation
            explanation_gen = get_explanation_generator()
            explanation_text = explanation_gen.generate_explanation(
                subject,
                prediction,
                confidence,
                top_features
            )

            # 6. Calculate priority score
            priority_score = self._calculate_priority_score(
                prediction["days_until_shortage"],
                confidence["confidence_score"],
                prediction["severity"]
            )

            is_critical = self._is_critical(
                prediction["days_until_shortage"],
                confidence["confidence_score"],
                prediction["severity"]
            )

            # 7. Check if prediction should be created (significant change)
            should_create = await self._should_create_prediction(
                subject,
                horizon,
                prediction["shortage_probability"]
            )

            if not should_create:
                logger.info(f"Skipping prediction for {subject} {horizon} - no significant change")
                return None

            # 8. Store prediction and explanation
            prediction_id = f"pred_{uuid.uuid4().hex[:12]}"

            await self._store_prediction(
                prediction_id=prediction_id,
                subject=subject,
                prediction=prediction,
                confidence=confidence,
                priority_score=priority_score,
                is_critical=is_critical
            )

            await self._store_explanation(
                prediction_id=prediction_id,
                top_features=top_features,
                explanation_text=explanation_text
            )

            logger.info(f"Created prediction {prediction_id} for {subject} {horizon}")

            return {
                "prediction_id": prediction_id,
                "subject": subject,
                **prediction,
                **confidence,
                "priority_score": priority_score,
                "is_critical": is_critical,
                "top_features": top_features,
                "explanation_text": explanation_text
            }

        except Exception as e:
            logger.error(f"Failed to generate prediction for {subject} {horizon}: {e}", exc_info=True)
            return None

    async def generate_predictions_for_all_subjects(
        self,
        horizons: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate predictions for all subjects across all horizons.

        Args:
            horizons: List of horizons to predict (default: all)

        Returns:
            Summary of predictions created
        """
        if horizons is None:
            horizons = self.horizons

        logger.info(f"Generating predictions for all subjects, horizons: {horizons}")

        start_time = datetime.utcnow()

        # Get all subjects
        async with AsyncSessionLocal() as session:
            query = text("SELECT DISTINCT subject FROM enrollments ORDER BY subject")
            result = await session.execute(query)
            subjects = [row.subject for row in result.fetchall()]

        total_predictions = 0
        predictions_by_subject = {}

        for subject in subjects:
            subject_predictions = []

            for horizon in horizons:
                prediction = await self.generate_prediction_for_subject(subject, horizon)
                if prediction:
                    subject_predictions.append(prediction)
                    total_predictions += 1

            predictions_by_subject[subject] = len(subject_predictions)

        duration = (datetime.utcnow() - start_time).total_seconds()

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "subjects_analyzed": len(subjects),
            "horizons": horizons,
            "predictions_created": total_predictions,
            "predictions_by_subject": predictions_by_subject,
            "duration_seconds": duration
        }

        logger.info(f"Prediction run complete: {total_predictions} predictions in {duration:.1f}s")

        return summary

    def _calculate_priority_score(
        self,
        days_until: int,
        confidence: float,
        severity: str
    ) -> float:
        """
        Calculate priority score for prediction.

        Formula: (1 / days_until) × (confidence / 100) × severity_multiplier

        Args:
            days_until: Days until shortage
            confidence: Confidence score (0-100)
            severity: Severity level (low/medium/high)

        Returns:
            Priority score (0-100)
        """
        # Urgency component (inverse of days)
        if days_until <= 0:
            urgency = 1.0
        else:
            urgency = 1.0 / max(days_until, 1)

        # Normalize urgency to reasonable scale
        # 7 days = high urgency (1.0), 56 days = low urgency (~0.125)
        urgency_normalized = min(urgency * 7, 1.0)

        # Confidence component (0-1 scale)
        confidence_normalized = confidence / 100.0

        # Severity multiplier
        severity_multipliers = {
            "low": 0.5,
            "medium": 0.75,
            "high": 1.0
        }
        severity_multiplier = severity_multipliers.get(severity, 0.75)

        # Calculate priority
        priority = urgency_normalized * confidence_normalized * severity_multiplier

        # Scale to 0-100
        priority_score = priority * 100

        return round(priority_score, 2)

    def _is_critical(
        self,
        days_until: int,
        confidence: float,
        severity: str
    ) -> bool:
        """
        Determine if prediction is critical.

        Critical if: <14 days AND >70% confidence AND severity high

        Args:
            days_until: Days until shortage
            confidence: Confidence score
            severity: Severity level

        Returns:
            True if critical
        """
        return (
            days_until < 14 and
            confidence > 70 and
            severity == "high"
        )

    async def _should_create_prediction(
        self,
        subject: str,
        horizon: str,
        new_probability: float
    ) -> bool:
        """
        Check if prediction should be created.

        Only create if probability changed significantly (>10%) or no existing prediction.

        Args:
            subject: Subject name
            horizon: Prediction horizon
            new_probability: New shortage probability

        Returns:
            True if prediction should be created
        """
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT shortage_probability
                FROM predictions
                WHERE subject = :subject
                AND horizon = :horizon
                AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            result = await session.execute(query, {
                "subject": subject,
                "horizon": horizon
            })
            row = result.fetchone()

            if not row:
                # No existing prediction, create new one
                return True

            old_probability = row.shortage_probability
            probability_change = abs(new_probability - old_probability)

            # Create if change > 10%
            return probability_change > self.probability_threshold

    async def _store_prediction(
        self,
        prediction_id: str,
        subject: str,
        prediction: Dict[str, Any],
        confidence: Dict[str, Any],
        priority_score: float,
        is_critical: bool
    ):
        """Store prediction in database"""
        async with AsyncSessionLocal() as session:
            query = text("""
                INSERT INTO predictions (
                    prediction_id, subject,
                    shortage_probability, predicted_shortage_date,
                    days_until_shortage, severity, predicted_peak_utilization,
                    horizon, horizon_days,
                    confidence_score, confidence_level, confidence_breakdown,
                    priority_score, is_critical,
                    status, created_at, updated_at
                ) VALUES (
                    :prediction_id, :subject,
                    :shortage_probability, :predicted_shortage_date,
                    :days_until_shortage, :severity, :predicted_peak_utilization,
                    :horizon, :horizon_days,
                    :confidence_score, :confidence_level, :confidence_breakdown,
                    :priority_score, :is_critical,
                    'active', NOW(), NOW()
                )
            """)

            await session.execute(query, {
                "prediction_id": prediction_id,
                "subject": subject,
                "shortage_probability": prediction["shortage_probability"],
                "predicted_shortage_date": prediction["predicted_shortage_date"],
                "days_until_shortage": prediction["days_until_shortage"],
                "severity": prediction["severity"],
                "predicted_peak_utilization": prediction["predicted_peak_utilization"],
                "horizon": prediction["horizon"],
                "horizon_days": prediction["horizon_days"],
                "confidence_score": confidence["confidence_score"],
                "confidence_level": confidence["confidence_level"],
                "confidence_breakdown": confidence["breakdown"],
                "priority_score": priority_score,
                "is_critical": is_critical
            })
            await session.commit()

    async def _store_explanation(
        self,
        prediction_id: str,
        top_features: List[Dict[str, Any]],
        explanation_text: str
    ):
        """Store explanation in database"""
        async with AsyncSessionLocal() as session:
            query = text("""
                INSERT INTO explanations (
                    prediction_id, top_features, explanation_text, created_at
                ) VALUES (
                    :prediction_id, :top_features, :explanation_text, NOW()
                )
            """)

            await session.execute(query, {
                "prediction_id": prediction_id,
                "top_features": top_features,
                "explanation_text": explanation_text
            })
            await session.commit()


# Singleton instance
_prediction_service_instance = None


def get_prediction_service() -> PredictionService:
    """Get singleton PredictionService instance"""
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = PredictionService()
    return _prediction_service_instance

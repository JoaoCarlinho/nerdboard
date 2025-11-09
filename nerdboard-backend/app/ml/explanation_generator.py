"""
Explanation Text Generation

Generates human-readable natural language explanations for predictions.
Uses templates with dynamic data insertion.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ExplanationGenerator:
    """
    Generates natural language explanations for shortage predictions.

    Produces operations-manager-friendly text without technical jargon.
    """

    def generate_explanation(
        self,
        subject: str,
        prediction: Dict[str, Any],
        confidence: Dict[str, Any],
        top_features: List[Dict[str, Any]]
    ) -> str:
        """
        Generate complete natural language explanation.

        Args:
            subject: Subject name
            prediction: Prediction dictionary
            confidence: Confidence calculation dictionary
            top_features: Top contributing features from SHAP

        Returns:
            Natural language explanation text
        """
        # Extract key metrics
        shortage_prob = prediction.get("shortage_probability", 0) * 100
        days_until = prediction.get("days_until_shortage", 0)
        severity = prediction.get("severity", "medium")
        confidence_score = confidence.get("confidence_score", 0)

        # Build explanation sections
        sections = []

        # 1. Main prediction statement
        main_statement = self._generate_main_statement(
            subject, shortage_prob, days_until, severity
        )
        sections.append(main_statement)

        # 2. Top contributing factors
        factors_section = self._generate_factors_section(top_features)
        sections.append(factors_section)

        # 3. Confidence reasoning
        confidence_section = self._generate_confidence_section(confidence)
        sections.append(confidence_section)

        # 4. Historical context (if available)
        historical_section = self._generate_historical_context(subject, top_features)
        if historical_section:
            sections.append(historical_section)

        # 5. Recommendation
        recommendation = self._generate_recommendation(days_until, severity, shortage_prob)
        sections.append(recommendation)

        # Combine all sections
        explanation = "\n\n".join(sections)

        return explanation

    def _generate_main_statement(
        self,
        subject: str,
        shortage_prob: float,
        days_until: int,
        severity: str
    ) -> str:
        """Generate main prediction statement"""
        if shortage_prob >= 70:
            certainty = "will likely"
        elif shortage_prob >= 50:
            certainty = "may"
        else:
            certainty = "has a low probability to"

        severity_desc = {
            "low": "minor capacity strain",
            "medium": "moderate capacity shortage",
            "high": "severe capacity shortage"
        }.get(severity, "capacity shortage")

        if days_until <= 7:
            timeframe = "within the next week"
        elif days_until <= 14:
            timeframe = f"in approximately {days_until} days"
        elif days_until <= 30:
            timeframe = f"in about {days_until // 7} weeks"
        else:
            timeframe = f"in approximately {days_until // 30} months"

        return (
            f"Based on current trends, {subject} tutoring capacity {certainty} experience "
            f"{severity_desc} {timeframe} (estimated {shortage_prob:.0f}% probability)."
        )

    def _generate_factors_section(self, top_features: List[Dict[str, Any]]) -> str:
        """Generate top contributing factors section"""
        if not top_features:
            return "Key factors contributing to this prediction are being analyzed."

        # Get top 3 most important factors
        top_3 = top_features[:3]

        factors_text = "This prediction is primarily driven by:\n"

        for i, feature in enumerate(top_3, 1):
            desc = feature.get("readable_description", "Unknown factor")
            # Clean up the description to remove technical suffix
            desc = desc.replace(" (increasing shortage risk)", "").replace(" (decreasing shortage risk)", "")
            factors_text += f"{i}. {desc}\n"

        return factors_text.strip()

    def _generate_confidence_section(self, confidence: Dict[str, Any]) -> str:
        """Generate confidence reasoning section"""
        confidence_score = confidence.get("confidence_score", 0)
        breakdown = confidence.get("breakdown", {})

        model_certainty = breakdown.get("model_certainty", 0)
        data_quality = breakdown.get("data_quality", 0)
        pattern_strength = breakdown.get("pattern_strength", 0)

        # Determine confidence description
        if confidence_score >= 80:
            confidence_desc = "high confidence"
        elif confidence_score >= 60:
            confidence_desc = "moderate confidence"
        else:
            confidence_desc = "limited confidence"

        # Build reasoning
        reasoning_parts = []

        if model_certainty >= 70:
            reasoning_parts.append("strong statistical correlation")
        if data_quality >= 80:
            reasoning_parts.append("high data quality")
        if pattern_strength >= 70:
            reasoning_parts.append("clear trend patterns")

        if reasoning_parts:
            reasoning = ", ".join(reasoning_parts)
            return (
                f"We have {confidence_desc} in this prediction ({confidence_score:.0f}%) "
                f"based on {reasoning}."
            )
        else:
            return f"Confidence in this prediction is {confidence_score:.0f}%."

    def _generate_historical_context(
        self,
        subject: str,
        top_features: List[Dict[str, Any]]
    ) -> str:
        """Generate historical context section"""
        # Check for seasonal patterns in features
        seasonal_features = [f for f in top_features
                            if "seasonal" in f.get("feature", "").lower()
                            or "back_to_school" in f.get("feature", "").lower()]

        if not seasonal_features:
            return ""

        # Extract seasonal information
        for feature in seasonal_features:
            feature_name = feature.get("feature", "")

            if "is_back_to_school_season" in feature_name:
                return (
                    "This pattern is consistent with historical back-to-school enrollment surges "
                    "typically observed in September and October."
                )
            elif "is_summer_season" in feature_name:
                return (
                    "This forecast accounts for typical summer enrollment patterns, "
                    "which historically show reduced demand during June through August."
                )
            elif "seasonal_factor" in feature_name:
                factor = feature.get("feature_value", 1.0)
                if factor > 1.2:
                    return (
                        f"Current enrollment is {factor*100:.0f}% of the yearly average, "
                        "indicating an above-normal seasonal surge."
                    )
                elif factor < 0.8:
                    return (
                        f"Current enrollment is {factor*100:.0f}% of the yearly average, "
                        "reflecting a typical seasonal downturn."
                    )

        return ""

    def _generate_recommendation(
        self,
        days_until: int,
        severity: str,
        shortage_prob: float
    ) -> str:
        """Generate actionable recommendation"""
        if days_until <= 7 and severity == "high":
            return (
                "⚠️ URGENT: Immediate action recommended. Consider temporary capacity expansion, "
                "prioritizing existing student commitments, or pausing new enrollments."
            )
        elif days_until <= 14 and shortage_prob >= 70:
            return (
                "Action recommended within the next week. Review tutor availability, "
                "consider recruiting additional tutors, or adjust enrollment targets."
            )
        elif days_until <= 30:
            return (
                "Monitor closely and begin planning capacity adjustments. "
                "Consider proactive tutor recruitment or redistribution of resources from lower-demand subjects."
            )
        else:
            return (
                "Advance notice allows for strategic planning. Continue monitoring trends "
                "and consider long-term capacity planning initiatives."
            )


# Singleton instance
_explanation_generator_instance = None


def get_explanation_generator() -> ExplanationGenerator:
    """Get singleton ExplanationGenerator instance"""
    global _explanation_generator_instance
    if _explanation_generator_instance is None:
        _explanation_generator_instance = ExplanationGenerator()
    return _explanation_generator_instance

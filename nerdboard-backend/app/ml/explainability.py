"""
SHAP Explainability Integration

Generates SHAP values for model predictions to provide explanations.
Maps feature importance to human-readable descriptions.
"""
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# SHAP is optional dependency - graceful degradation if not available
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP library not available. Falling back to feature importance.")


class ExplainabilityEngine:
    """
    Generates explanations for ML predictions using SHAP values.

    Identifies top contributing features and maps them to readable descriptions.
    """

    def __init__(self, model=None, feature_columns: Optional[List[str]] = None):
        """
        Initialize explainability engine.

        Args:
            model: Trained model (Random Forest, GB, etc.)
            feature_columns: List of feature column names
        """
        self.model = model
        self.feature_columns = feature_columns
        self.explainer = None

        if SHAP_AVAILABLE and model is not None:
            try:
                # Use TreeExplainer for tree-based models
                self.explainer = shap.TreeExplainer(model)
                logger.info("SHAP TreeExplainer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize SHAP explainer: {e}")
                self.explainer = None

    def explain_prediction(
        self,
        features: Dict[str, float],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate SHAP-based explanation for a prediction.

        Args:
            features: Feature dictionary
            top_n: Number of top features to return

        Returns:
            List of top contributing features with SHAP values and descriptions
        """
        if self.explainer is not None and SHAP_AVAILABLE:
            return self._explain_with_shap(features, top_n)
        else:
            return self._explain_with_feature_importance(features, top_n)

    def _explain_with_shap(
        self,
        features: Dict[str, float],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """Generate explanation using SHAP values"""
        try:
            # Convert features to DataFrame
            feature_df = pd.DataFrame([features])

            # Ensure all expected columns present
            for col in self.feature_columns:
                if col not in feature_df.columns:
                    feature_df[col] = 0.0

            feature_df = feature_df[self.feature_columns]

            # Calculate SHAP values
            shap_values = self.explainer.shap_values(feature_df)

            # For binary classification, use positive class SHAP values
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Positive class (shortage)

            # Get feature contributions
            contributions = []
            for i, col in enumerate(self.feature_columns):
                shap_value = shap_values[0][i]
                feature_value = feature_df.iloc[0][col]

                contributions.append({
                    "feature": col,
                    "shap_value": float(shap_value),
                    "feature_value": float(feature_value),
                    "importance": abs(shap_value)
                })

            # Sort by absolute SHAP value and take top N
            top_features = sorted(contributions, key=lambda x: x["importance"], reverse=True)[:top_n]

            # Add readable descriptions
            for feature in top_features:
                feature["readable_description"] = self._get_readable_description(
                    feature["feature"],
                    feature["feature_value"],
                    feature["shap_value"]
                )

            return top_features

        except Exception as e:
            logger.error(f"SHAP explanation failed: {e}", exc_info=True)
            return self._explain_with_feature_importance(features, top_n)

    def _explain_with_feature_importance(
        self,
        features: Dict[str, float],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """Fallback: Use model feature importance instead of SHAP"""
        if self.model is None or not hasattr(self.model, 'feature_importances_'):
            # Ultimate fallback: Use feature values themselves
            sorted_features = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
            return [
                {
                    "feature": feat,
                    "shap_value": val,  # Using feature value as proxy
                    "feature_value": val,
                    "importance": abs(val),
                    "readable_description": self._get_readable_description(feat, val, val)
                }
                for feat, val in sorted_features
            ]

        # Use model's feature importances
        importances = self.model.feature_importances_
        contributions = []

        for i, col in enumerate(self.feature_columns):
            importance = importances[i]
            feature_value = features.get(col, 0.0)

            # Contribution = importance × feature value
            contribution = importance * feature_value

            contributions.append({
                "feature": col,
                "shap_value": float(contribution),
                "feature_value": float(feature_value),
                "importance": float(importance)
            })

        # Sort and take top N
        top_features = sorted(contributions, key=lambda x: x["importance"], reverse=True)[:top_n]

        # Add readable descriptions
        for feature in top_features:
            feature["readable_description"] = self._get_readable_description(
                feature["feature"],
                feature["feature_value"],
                feature["shap_value"]
            )

        return top_features

    def _get_readable_description(
        self,
        feature_name: str,
        feature_value: float,
        shap_value: float
    ) -> str:
        """
        Convert technical feature name to human-readable description.

        Args:
            feature_name: Technical feature name
            feature_value: Feature value
            shap_value: SHAP contribution value

        Returns:
            Human-readable description
        """
        # Determine impact direction
        impact = "increasing" if shap_value > 0 else "decreasing"

        # Map feature names to readable descriptions
        if "enrollment_velocity" in feature_name:
            if feature_value > 0:
                return f"Enrollment spike detected: +{feature_value*100:.1f}% week-over-week ({impact} shortage risk)"
            else:
                return f"Enrollment decline: {feature_value*100:.1f}% week-over-week ({impact} shortage risk)"

        elif "utilization_trend" in feature_name:
            if feature_value > 0:
                return f"Utilization trending upward: +{feature_value:.1f}% per week ({impact} shortage risk)"
            else:
                return f"Utilization declining: {feature_value:.1f}% per week ({impact} shortage risk)"

        elif "utilization_current_week" in feature_name:
            return f"Current utilization at {feature_value:.1f}% ({impact} shortage risk)"

        elif "seasonal_factor" in feature_name:
            if feature_value > 1.2:
                return f"Seasonal spike: {feature_value*100:.0f}% of yearly average ({impact} shortage risk)"
            elif feature_value < 0.8:
                return f"Seasonal dip: {feature_value*100:.0f}% of yearly average ({impact} shortage risk)"
            else:
                return f"Normal seasonal pattern ({impact} shortage risk)"

        elif "is_back_to_school_season" in feature_name and feature_value > 0:
            return f"Back-to-school season active ({impact} shortage risk)"

        elif "is_summer_season" in feature_name and feature_value > 0:
            return f"Summer season (typically lower demand) ({impact} shortage risk)"

        elif "tutor_count" in feature_name:
            return f"Tutor availability: {feature_value:.0f} tutors ({impact} shortage risk)"

        elif "session_rate" in feature_name:
            return f"Session booking rate: {feature_value:.1f} sessions/day ({impact} shortage risk)"

        elif "enrollment_rate" in feature_name:
            return f"Enrollment rate: {feature_value:.1f} students/day ({impact} shortage risk)"

        elif "total_capacity_hours" in feature_name:
            return f"Total capacity: {feature_value:.0f} hours/week ({impact} shortage risk)"

        else:
            # Generic description
            return f"{feature_name.replace('_', ' ').title()}: {feature_value:.2f} ({impact} shortage risk)"


def create_explainability_engine(model, feature_columns: List[str]) -> ExplainabilityEngine:
    """
    Factory function to create ExplainabilityEngine.

    Args:
        model: Trained ML model
        feature_columns: List of feature names

    Returns:
        ExplainabilityEngine instance
    """
    return ExplainabilityEngine(model, feature_columns)

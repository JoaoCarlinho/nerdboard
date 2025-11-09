"""
Capacity Shortage Prediction Model

ML model that predicts shortage probability using Random Forest.
Predicts: shortage_probability, predicted_shortage_date, severity.
"""
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sqlalchemy import text

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ShortagePredictor:
    """
    Machine learning model for predicting capacity shortages.

    Uses Random Forest to predict shortage probability at different time horizons.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize predictor.

        Args:
            model_path: Path to saved model file (default: models/shortage_predictor_v1.pkl)
        """
        if model_path is None:
            model_path = "models/shortage_predictor_v1.pkl"

        self.model_path = model_path
        self.model = None
        self.feature_columns = None
        self.shortage_threshold = 0.95  # 95% utilization = shortage

        # Prediction horizons (in weeks)
        self.horizons = {
            "2week": 14,
            "4week": 28,
            "6week": 42,
            "8week": 56
        }

    def load_model(self):
        """Load trained model from disk"""
        if os.path.exists(self.model_path):
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
                self.model = model_data['model']
                self.feature_columns = model_data['feature_columns']
            logger.info(f"Loaded model from {self.model_path}")
        else:
            logger.warning(f"Model file not found: {self.model_path}")
            self.model = None

    def save_model(self):
        """Save trained model to disk"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        model_data = {
            'model': self.model,
            'feature_columns': self.feature_columns,
            'trained_at': datetime.utcnow().isoformat(),
            'shortage_threshold': self.shortage_threshold
        }

        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Saved model to {self.model_path}")

    async def prepare_training_data(
        self,
        horizon_days: int = 14
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training dataset from historical features and outcomes.

        Args:
            horizon_days: Prediction horizon in days

        Returns:
            (X, y) tuple of features and labels
        """
        logger.info(f"Preparing training data for {horizon_days}-day horizon")

        async with AsyncSessionLocal() as session:
            # Get features with their reference dates
            query_features = text("""
                SELECT
                    subject,
                    reference_date,
                    features_json
                FROM prediction_features
                ORDER BY reference_date
            """)
            result = await session.execute(query_features)
            feature_rows = result.fetchall()

            training_data = []

            for row in feature_rows:
                subject = row.subject
                reference_date = row.reference_date
                features = row.features_json

                # Look ahead to see if shortage occurred
                future_date_start = reference_date + timedelta(days=1)
                future_date_end = reference_date + timedelta(days=horizon_days)

                # Check if utilization exceeded threshold in the horizon
                query_shortage = text("""
                    SELECT
                        COALESCE(MAX(utilization_rate), 0) as max_utilization
                    FROM (
                        SELECT
                            COALESCE(SUM(s.duration_minutes) / 60.0, 0) /
                            NULLIF(COALESCE(SUM(t.weekly_capacity_hours), 0), 0) as utilization_rate
                        FROM tutors t
                        LEFT JOIN sessions s ON
                            s.subject = :subject AND
                            s.scheduled_time >= :start_date AND
                            s.scheduled_time < :end_date
                        WHERE :subject = ANY(t.subjects)
                        GROUP BY DATE_TRUNC('week', s.scheduled_time)
                    ) weekly_utils
                """)

                result_shortage = await session.execute(query_shortage, {
                    "subject": subject,
                    "start_date": future_date_start,
                    "end_date": future_date_end
                })
                max_util = result_shortage.fetchone().max_utilization

                # Label: 1 if shortage occurred, 0 otherwise
                shortage_occurred = 1 if max_util >= self.shortage_threshold else 0

                training_data.append({
                    **features,
                    'target': shortage_occurred,
                    'max_future_utilization': max_util
                })

        if not training_data:
            logger.warning("No training data available")
            return pd.DataFrame(), pd.Series()

        # Convert to DataFrame
        df = pd.DataFrame(training_data)

        # Separate features and target
        y = df['target']
        X = df.drop(columns=['target', 'max_future_utilization'])

        # Store feature columns
        self.feature_columns = X.columns.tolist()

        logger.info(f"Training data prepared: {len(X)} samples, {len(self.feature_columns)} features")
        logger.info(f"Shortage cases: {y.sum()} ({y.sum()/len(y)*100:.1f}%)")

        return X, y

    def train_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        tune_hyperparameters: bool = False
    ) -> Dict[str, float]:
        """
        Train Random Forest model.

        Args:
            X: Feature matrix
            y: Target labels
            tune_hyperparameters: Whether to perform grid search (slower but better)

        Returns:
            Dictionary of training metrics
        """
        logger.info("Training Random Forest model...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        if tune_hyperparameters:
            # Grid search for best hyperparameters
            param_grid = {
                'n_estimators': [50, 100, 200],
                'max_depth': [10, 20, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }

            rf = RandomForestClassifier(random_state=42)
            grid_search = GridSearchCV(
                rf, param_grid, cv=3, scoring='f1', n_jobs=-1, verbose=1
            )
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_

            logger.info(f"Best params: {grid_search.best_params_}")
        else:
            # Use default params for speed
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=20,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }

        logger.info(f"Model trained: Accuracy={metrics['accuracy']:.2%}, F1={metrics['f1_score']:.2%}")

        return metrics

    def predict_shortage(
        self,
        features: Dict[str, float],
        horizon: str = "2week"
    ) -> Dict[str, Any]:
        """
        Predict shortage probability for given features.

        Args:
            features: Feature dictionary
            horizon: Prediction horizon (2week, 4week, 6week, 8week)

        Returns:
            Prediction dictionary with probability, date, severity
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        # Convert features to DataFrame with correct column order
        feature_df = pd.DataFrame([features])

        # Ensure all expected columns are present
        for col in self.feature_columns:
            if col not in feature_df.columns:
                feature_df[col] = 0.0  # Default value for missing features

        # Select only the columns used in training
        feature_df = feature_df[self.feature_columns]

        # Predict
        shortage_probability = self.model.predict_proba(feature_df)[0, 1]

        # Calculate predicted shortage date
        horizon_days = self.horizons.get(horizon, 14)
        reference_date = datetime.utcnow()

        # Estimate when shortage will occur based on utilization trend
        current_utilization = features.get('utilization_current_week', 0)
        utilization_trend = features.get('utilization_trend', 0)

        if utilization_trend > 0:
            # Calculate days until 95% utilization
            days_until = (self.shortage_threshold * 100 - current_utilization) / utilization_trend
            days_until = max(0, min(days_until, horizon_days))
        else:
            # Use probability to estimate
            days_until = horizon_days * (1 - shortage_probability)

        predicted_shortage_date = reference_date + timedelta(days=days_until)

        # Calculate severity (how bad the shortage will be)
        predicted_peak_utilization = current_utilization + (utilization_trend * days_until)
        shortage_amount = max(0, predicted_peak_utilization - (self.shortage_threshold * 100))
        severity = "low" if shortage_amount < 10 else "medium" if shortage_amount < 20 else "high"

        return {
            "shortage_probability": float(shortage_probability),
            "predicted_shortage_date": predicted_shortage_date.isoformat(),
            "days_until_shortage": int(days_until),
            "severity": severity,
            "predicted_peak_utilization": float(predicted_peak_utilization),
            "horizon": horizon,
            "horizon_days": horizon_days
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores from trained model"""
        if self.model is None or self.feature_columns is None:
            return {}

        importances = self.model.feature_importances_
        return dict(zip(self.feature_columns, importances))


# Singleton instance
_predictor_instance = None


def get_shortage_predictor() -> ShortagePredictor:
    """Get singleton ShortagePredictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = ShortagePredictor()
        _predictor_instance.load_model()
    return _predictor_instance

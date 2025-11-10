"""
Prediction Model

Stores ML predictions for tutor shortage forecasts with confidence scores.
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class Prediction(Base):
    """
    Shortage prediction model with confidence metrics.

    Stores predictions from the ML model including shortage probability,
    confidence scores, priority, and SHAP explanations.
    """
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id = Column(String(100), unique=True, nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)

    # Prediction outputs
    shortage_probability = Column(Float, nullable=False)  # 0.0 to 1.0
    predicted_shortage_date = Column(DateTime(timezone=True), nullable=True)
    days_until_shortage = Column(Integer, nullable=False)
    predicted_peak_utilization = Column(Float, nullable=True)

    # Confidence metrics
    confidence_score = Column(Float, nullable=False)  # 0-100
    confidence_level = Column(String(20), nullable=True)  # low/medium/high
    confidence_breakdown = Column(Text, nullable=True)  # JSON string

    # Priority and severity
    severity = Column(String(20), nullable=False)  # critical/high/medium/low
    priority_score = Column(Float, nullable=False)  # 0-100
    is_critical = Column(Boolean, default=False, nullable=False)

    # Prediction configuration
    horizon = Column(String(20), nullable=True)  # 2week, 4week, 6week, 8week
    horizon_days = Column(Integer, nullable=True)

    # Status and metadata
    status = Column(String(20), default="active", nullable=False)  # active/resolved/expired
    explanation_text = Column(Text, nullable=True)
    shap_values = Column(Text, nullable=True)  # JSON string of SHAP values

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Prediction(id={self.prediction_id}, subject={self.subject}, probability={self.shortage_probability})>"

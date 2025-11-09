"""
Prediction Features Model

Stores extracted time-series features for ML model input.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PredictionFeature(Base):
    """
    Prediction features table.

    Stores feature engineering outputs for each subject and date.
    """
    __tablename__ = "prediction_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(100), nullable=False, index=True)
    reference_date = Column(DateTime, nullable=False, index=True)
    features_json = Column(JSON, nullable=False)  # All extracted features
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('subject', 'reference_date', name='uq_subject_reference_date'),
    )

    def __repr__(self):
        return f"<PredictionFeature(subject='{self.subject}', reference_date='{self.reference_date}')>"

"""HealthMetric model - Customer health tracking for churn prediction"""
from sqlalchemy import Column, String, Integer, Float, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class HealthMetric(Base):
    """Customer health metrics for churn and capacity planning"""

    __tablename__ = "health_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(100), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    health_score = Column(
        Float,
        CheckConstraint("health_score >= 0 AND health_score <= 100"),
        nullable=False,
    )
    engagement_level = Column(Integer, nullable=True)
    support_ticket_count = Column(Integer, nullable=True)
    session_completion_rate = Column(
        Float,
        CheckConstraint("session_completion_rate >= 0 AND session_completion_rate <= 1"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_health_customer_date", "customer_id", "date", postgresql_ops={"date": "DESC"}),
    )

    def __repr__(self):
        return f"<HealthMetric(id={self.id}, customer={self.customer_id}, score={self.health_score})>"

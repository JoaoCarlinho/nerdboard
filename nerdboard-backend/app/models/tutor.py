"""Tutor model - Tutor resource availability and capacity"""
from sqlalchemy import Column, String, Integer, Float, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Tutor(Base):
    """Tutor resource with subjects and capacity tracking"""

    __tablename__ = "tutors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(String(100), unique=True, nullable=False)
    subjects = Column(ARRAY(String), nullable=False)
    weekly_capacity_hours = Column(Integer, nullable=False)
    utilization_rate = Column(
        Float,
        CheckConstraint("utilization_rate >= 0 AND utilization_rate <= 1"),
        nullable=True,
    )
    avg_response_time_hours = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_tutors_subjects", "subjects", postgresql_using="gin"),
        Index("idx_tutors_tutor_id", "tutor_id"),
    )

    def __repr__(self):
        return f"<Tutor(id={self.id}, tutor_id={self.tutor_id}, subjects={self.subjects})>"

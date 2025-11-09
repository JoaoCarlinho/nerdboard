"""Enrollment model - Tracks student enrollment in subjects"""
from sqlalchemy import Column, String, Float, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Enrollment(Base):
    """Student enrollment in a subject with engagement tracking"""

    __tablename__ = "enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), nullable=False)
    subject = Column(String(100), nullable=False)
    cohort_id = Column(String(50), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    engagement_score = Column(
        Float,
        CheckConstraint("engagement_score >= 0 AND engagement_score <= 1"),
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
        Index("idx_enrollments_subject_date", "subject", "start_date"),
        Index("idx_enrollments_student", "student_id"),
    )

    def __repr__(self):
        return f"<Enrollment(id={self.id}, student={self.student_id}, subject={self.subject})>"

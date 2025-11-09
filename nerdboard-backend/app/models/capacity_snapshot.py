"""CapacitySnapshot model - Daily capacity tracking per subject"""
from sqlalchemy import Column, String, Integer, Float, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class CapacitySnapshot(Base):
    """Daily capacity snapshot for subject-level capacity tracking"""

    __tablename__ = "capacity_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject = Column(String(100), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    total_capacity_hours = Column(Integer, nullable=False)
    used_capacity_hours = Column(Integer, nullable=False)
    available_tutors_count = Column(Integer, nullable=False)
    utilization_rate = Column(
        Float,
        CheckConstraint("utilization_rate >= 0 AND utilization_rate <= 1"),
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
        Index("idx_capacity_subject_date", "subject", "date", postgresql_ops={"date": "DESC"}),
    )

    def __repr__(self):
        return f"<CapacitySnapshot(id={self.id}, subject={self.subject}, date={self.date})>"

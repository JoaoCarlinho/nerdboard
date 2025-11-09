"""DataQualityLog model - Data quality monitoring and validation"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class DataQualityLog(Base):
    """Data quality check log for monitoring and alerting"""

    __tablename__ = "data_quality_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False)  # e.g., 'passed', 'failed', 'warning'
    quality_score = Column(
        Float,
        CheckConstraint("quality_score >= 0 AND quality_score <= 5"),
        nullable=True,
    )
    affected_records_count = Column(Integer, nullable=True)
    error_details = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_quality_check_status", "check_name", "status"),
        Index("idx_quality_checked_at", "checked_at", postgresql_ops={"checked_at": "DESC"}),
    )

    def __repr__(self):
        return f"<DataQualityLog(id={self.id}, check={self.check_name}, status={self.status})>"

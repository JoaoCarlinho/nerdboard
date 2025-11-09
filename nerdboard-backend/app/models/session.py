"""Session model - Individual tutoring sessions"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Session(Base):
    """Individual tutoring session with tutor assignment"""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), unique=True, nullable=False)
    subject = Column(String(100), nullable=False)
    tutor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tutors.id", ondelete="SET NULL"),
        nullable=True,
    )
    student_id = Column(UUID(as_uuid=True), nullable=False)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_sessions_subject_time", "subject", "scheduled_time"),
        Index("idx_sessions_tutor", "tutor_id"),
        Index("idx_sessions_student", "student_id"),
    )

    def __repr__(self):
        return f"<Session(id={self.id}, session_id={self.session_id}, subject={self.subject})>"

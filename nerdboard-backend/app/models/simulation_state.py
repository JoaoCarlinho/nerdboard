"""SimulationState model - Global simulation state (single-row table)"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func

from app.database import Base


class SimulationState(Base):
    """Global simulation state - single-row table with id=1 constraint"""

    __tablename__ = "simulation_state"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=False,
        default=1,
    )
    current_date = Column(DateTime(timezone=True), nullable=True)
    speed_multiplier = Column(Integer, nullable=True, default=1)
    is_running = Column(Boolean, nullable=False, default=False)
    last_event = Column(String(500), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Ensure single-row table constraint
    __table_args__ = (CheckConstraint("id = 1", name="single_row_check"),)

    def __repr__(self):
        return f"<SimulationState(id={self.id}, is_running={self.is_running}, speed={self.speed_multiplier})>"

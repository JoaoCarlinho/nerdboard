"""
Capacity API Endpoints

GET /api/v1/capacity/:subject - Query current capacity for a subject
POST /api/v1/capacity/recalculate-all - Admin endpoint to recalculate all subjects
"""

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from typing import Dict, Any

from app.services.capacity_calculator import get_capacity_calculator, SUBJECTS

router = APIRouter(prefix="/capacity", tags=["capacity"])


class WindowMetrics(BaseModel):
    """Metrics for a single time window"""
    total_hours: float
    booked_hours: float
    utilization_rate: float
    status: str
    window_start: str
    window_end: str


class CapacityResponse(BaseModel):
    """Response for GET /capacity/:subject"""
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class BulkRecalculateResponse(BaseModel):
    """Response for POST /capacity/recalculate-all"""
    data: Dict[str, Any]


@router.get("/{subject}", response_model=CapacityResponse)
async def get_subject_capacity(
    subject: str = Path(..., description="Subject name (e.g., Physics, Math)")
):
    """
    Get current capacity metrics for a subject across all time windows (AC-5).

    Args:
        subject: Subject name (must be in SUBJECTS list)

    Returns:
        JSON response with capacity metrics for 4 time windows:
        - current_week
        - next_2_weeks
        - next_4_weeks
        - next_8_weeks

    Raises:
        404: If subject not found in SUBJECTS
        500: If capacity calculation fails
    """
    # Validate subject
    if subject not in SUBJECTS:
        raise HTTPException(
            status_code=404,
            detail=f"Subject '{subject}' not found. Valid subjects: {SUBJECTS}"
        )

    calculator = get_capacity_calculator()

    try:
        # Calculate capacity for all 4 time windows
        capacity_data = {"subject": subject}

        for window in ["current_week", "next_2_weeks", "next_4_weeks", "next_8_weeks"]:
            metrics = await calculator.calculate_subject_capacity(subject, window)
            capacity_data[window] = metrics

        return CapacityResponse(
            data=capacity_data,
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "cache_hit": False  # TODO: Implement caching in Task 7
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating capacity for {subject}: {str(e)}"
        )


@router.post("/recalculate-all", response_model=BulkRecalculateResponse)
async def recalculate_all_subjects():
    """
    Admin endpoint to recalculate capacity for all subjects (AC-1).

    Iterates through all subjects in SUBJECTS list and calculates capacity
    for all 4 time windows, saving snapshots to database.

    Returns:
        Summary with subjects_calculated, snapshots_created, duration_ms

    Raises:
        500: If bulk calculation fails
    """
    calculator = get_capacity_calculator()

    try:
        summary = await calculator.calculate_all_subjects_capacity()

        return BulkRecalculateResponse(data=summary)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during bulk recalculation: {str(e)}"
        )


# Import datetime at module level
from datetime import datetime

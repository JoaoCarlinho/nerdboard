"""
Simulation Control API Endpoints (AC-3, AC-4)

Provides REST API for controlling real-time simulation:
- POST /api/v1/simulation/start
- POST /api/v1/simulation/pause
- POST /api/v1/simulation/advance
- GET /api/v1/simulation/status
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.services.data_simulator import get_simulator

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


# Request/Response models
class AdvanceRequest(BaseModel):
    """Request model for advancing simulation"""
    days: int = Field(..., gt=0, le=365, description="Number of days to advance (1-365)")


class SimulationResponse(BaseModel):
    """Standard response wrapper"""
    data: Dict[str, Any]


@router.post("/start", response_model=SimulationResponse)
async def start_simulation():
    """
    Start real-time simulation (AC-4)

    Sets is_running=true and starts event generation scheduler.
    """
    try:
        simulator = get_simulator()
        result = await simulator.start_simulation()
        return SimulationResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start simulation: {str(e)}")


@router.post("/pause", response_model=SimulationResponse)
async def pause_simulation():
    """
    Pause simulation (AC-4)

    Sets is_running=false, stops event generation.
    """
    try:
        simulator = get_simulator()
        result = await simulator.pause_simulation()
        return SimulationResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause simulation: {str(e)}")


@router.post("/advance", response_model=SimulationResponse)
async def advance_simulation(request: AdvanceRequest):
    """
    Fast-forward simulation by N days (AC-4, AC-7)

    Advances current_simulation_time and generates batch events.
    Target: <5 seconds for 7-day advance.
    """
    try:
        simulator = get_simulator()
        result = await simulator.advance_simulation(days=request.days)
        return SimulationResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to advance simulation: {str(e)}")


@router.get("/status", response_model=SimulationResponse)
async def get_simulation_status():
    """
    Get current simulation status (AC-4)

    Returns current_time, is_running, speed_multiplier, last_event_time.
    """
    try:
        simulator = get_simulator()
        result = await simulator.get_status()
        return SimulationResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get simulation status: {str(e)}")


@router.get("/metrics", response_model=SimulationResponse)
async def get_simulation_metrics():
    """
    Get simulation performance metrics (AC-2)

    Returns events_per_second, avg_event_generation_time_ms, etc.
    """
    # TODO: Implement metrics tracking
    return SimulationResponse(data={
        "events_per_second": 0,
        "avg_event_generation_time_ms": 0,
        "total_events_generated": 0
    })

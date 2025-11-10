"""
Dashboard Data API Endpoints

Provides aggregated data for dashboard overview and metrics.
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import text

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# Pydantic models

class SubjectStatus(BaseModel):
    """Subject capacity status for overview"""
    subject: str
    current_utilization: float
    predicted_status: str  # ok, warning, critical
    active_alerts_count: int
    tutor_count: int
    total_capacity_hours: float


class DashboardOverviewResponse(BaseModel):
    """Dashboard overview response"""
    subjects: List[SubjectStatus]
    last_updated: str


class MetricsResponse(BaseModel):
    """Operational metrics response"""
    avg_health_score: float
    first_session_success_rate: float
    session_velocity: float
    churn_risk_count: int
    supply_demand_ratio: float
    last_updated: str


class SubjectDetailResponse(BaseModel):
    """Subject detail response"""
    subject: str
    current_utilization: float
    tutor_count: int
    capacity_hours: float
    predictions: List[Dict[str, Any]]
    utilization_history: List[Dict[str, Any]]
    tutors: List[Dict[str, Any]]


# API Endpoints

@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview() -> Dict[str, Any]:
    """
    Get dashboard overview with all subjects' capacity status.

    Returns current state for all subjects including utilization,
    predicted status, and active alert counts.

    Response time target: <500ms
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get all subjects with capacity and predictions
            query = text("""
                WITH subject_capacity AS (
                    SELECT
                        t.subjects[1] as subject,
                        COUNT(DISTINCT t.id) as tutor_count,
                        COALESCE(SUM(t.weekly_capacity_hours), 0) as total_capacity,
                        COALESCE(SUM(s.booked_hours), 0) as booked_hours
                    FROM tutors t
                    CROSS JOIN LATERAL (
                        SELECT SUM(duration_minutes) / 60.0 as booked_hours
                        FROM sessions
                        WHERE subject = t.subjects[1]
                        AND scheduled_time >= NOW() - INTERVAL '7 days'
                        AND scheduled_time <= NOW()
                    ) s
                    GROUP BY t.subjects[1]
                ),
                subject_predictions AS (
                    SELECT
                        subject,
                        COUNT(*) as alert_count
                    FROM predictions
                    WHERE status = 'active'
                    AND shortage_probability > 0.5
                    GROUP BY subject
                )
                SELECT
                    sc.subject,
                    sc.tutor_count,
                    sc.total_capacity,
                    CASE
                        WHEN sc.total_capacity > 0
                        THEN (sc.booked_hours / sc.total_capacity) * 100
                        ELSE 0
                    END as utilization,
                    COALESCE(sp.alert_count, 0) as alert_count
                FROM subject_capacity sc
                LEFT JOIN subject_predictions sp ON sc.subject = sp.subject
                ORDER BY sc.subject
            """)

            result = await session.execute(query)
            subjects = []

            for row in result.fetchall():
                utilization = float(row.utilization)

                # Determine predicted status
                if utilization >= 85 or row.alert_count > 0:
                    predicted_status = "critical"
                elif utilization >= 70:
                    predicted_status = "warning"
                else:
                    predicted_status = "ok"

                subjects.append({
                    "subject": row.subject,
                    "current_utilization": round(utilization, 2),
                    "predicted_status": predicted_status,
                    "active_alerts_count": row.alert_count,
                    "tutor_count": row.tutor_count,
                    "total_capacity_hours": float(row.total_capacity)
                })

            return {
                "subjects": subjects,
                "last_updated": "NOW()"  # Would use actual timestamp
            }

    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard overview: {str(e)}"
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_dashboard_metrics() -> Dict[str, Any]:
    """
    Get operational metrics for dashboard.

    Returns key performance indicators:
    - Average customer health score
    - First session success rate
    - Session velocity
    - Churn risk count
    - Supply vs demand ratio

    Response time target: <500ms
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get health scores
            query_health = text("""
                SELECT AVG(health_score) as avg_health
                FROM health_metrics
                WHERE date >= NOW() - INTERVAL '7 days'
            """)
            result_health = await session.execute(query_health)
            avg_health = result_health.fetchone().avg_health or 0.0

            # Get first session success rate (placeholder)
            # Would calculate from actual first session data
            first_session_success = 75.0

            # Get session velocity (sessions per week per student)
            query_velocity = text("""
                SELECT
                    COUNT(*)::float / NULLIF(COUNT(DISTINCT student_id), 0) as velocity
                FROM sessions
                WHERE scheduled_time >= NOW() - INTERVAL '7 days'
            """)
            result_velocity = await session.execute(query_velocity)
            velocity = result_velocity.fetchone().velocity or 0.0

            # Get churn risk count
            query_churn = text("""
                SELECT COUNT(DISTINCT customer_id) as count
                FROM health_metrics
                WHERE date >= NOW() - INTERVAL '14 days'
                AND health_score < 40
                AND support_ticket_count >= 2
            """)
            result_churn = await session.execute(query_churn)
            churn_count = result_churn.fetchone().count or 0

            # Calculate supply/demand ratio
            query_supply_demand = text("""
                SELECT
                    COALESCE(SUM(weekly_capacity_hours), 0) as supply,
                    COALESCE(SUM(booked_hours), 0) as demand
                FROM tutors t
                CROSS JOIN LATERAL (
                    SELECT SUM(duration_minutes) / 60.0 as booked_hours
                    FROM sessions
                    WHERE scheduled_time >= NOW() - INTERVAL '7 days'
                ) s
            """)
            result_sd = await session.execute(query_supply_demand)
            row_sd = result_sd.fetchone()
            supply = float(row_sd.supply) if row_sd.supply else 1.0
            demand = float(row_sd.demand) if row_sd.demand else 0.0
            supply_demand_ratio = supply / demand if demand > 0 else float('inf')

            return {
                "avg_health_score": round(float(avg_health), 2),
                "first_session_success_rate": round(first_session_success, 2),
                "session_velocity": round(float(velocity), 2),
                "churn_risk_count": int(churn_count),
                "supply_demand_ratio": round(supply_demand_ratio, 2),
                "last_updated": "NOW()"
            }

    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get("/subjects/{subject}", response_model=SubjectDetailResponse)
async def get_subject_detail(
    subject: str = Path(..., description="Subject name")
) -> Dict[str, Any]:
    """
    Get detailed view for a specific subject.

    Returns comprehensive data including capacity, utilization history,
    predictions, and tutor list.

    Response time target: <500ms
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get subject capacity
            query_capacity = text("""
                SELECT
                    COUNT(DISTINCT id) as tutor_count,
                    COALESCE(SUM(weekly_capacity_hours), 0) as total_capacity,
                    COALESCE(AVG(utilization_rate), 0) as avg_utilization
                FROM tutors
                WHERE :subject = ANY(subjects)
            """)
            result_cap = await session.execute(query_capacity, {"subject": subject})
            row_cap = result_cap.fetchone()

            # Get predictions for this subject
            query_predictions = text("""
                SELECT
                    prediction_id,
                    shortage_probability,
                    predicted_shortage_date,
                    days_until_shortage,
                    severity,
                    confidence_score,
                    priority_score
                FROM predictions
                WHERE subject = :subject
                AND status = 'active'
                ORDER BY priority_score DESC
                LIMIT 5
            """)
            result_pred = await session.execute(query_predictions, {"subject": subject})
            predictions = [
                {
                    "prediction_id": row.prediction_id,
                    "shortage_probability": float(row.shortage_probability),
                    "predicted_shortage_date": row.predicted_shortage_date.isoformat() if row.predicted_shortage_date else None,
                    "days_until_shortage": row.days_until_shortage,
                    "severity": row.severity,
                    "confidence_score": float(row.confidence_score),
                    "priority_score": float(row.priority_score)
                }
                for row in result_pred.fetchall()
            ]

            # Get utilization history (last 4 weeks)
            query_history = text("""
                SELECT
                    date_trunc('week', date) as week,
                    AVG(utilization_rate) * 100 as avg_utilization
                FROM capacity_snapshots
                WHERE subject = :subject
                AND date >= NOW() - INTERVAL '4 weeks'
                GROUP BY date_trunc('week', date)
                ORDER BY week DESC
            """)
            result_hist = await session.execute(query_history, {"subject": subject})
            utilization_history = [
                {
                    "week": row.week.isoformat(),
                    "utilization": round(float(row.avg_utilization), 2)
                }
                for row in result_hist.fetchall()
            ]

            # Get tutors for this subject
            query_tutors = text("""
                SELECT
                    tutor_id,
                    weekly_capacity_hours,
                    utilization_rate
                FROM tutors
                WHERE :subject = ANY(subjects)
                ORDER BY utilization_rate DESC
                LIMIT 20
            """)
            result_tutors = await session.execute(query_tutors, {"subject": subject})
            tutors = [
                {
                    "tutor_id": row.tutor_id,
                    "availability_hours": float(row.weekly_capacity_hours),
                    "utilization": float(row.utilization_rate) * 100
                }
                for row in result_tutors.fetchall()
            ]

            return {
                "subject": subject,
                "current_utilization": round(float(row_cap.avg_utilization) * 100, 2),
                "tutor_count": row_cap.tutor_count,
                "capacity_hours": float(row_cap.total_capacity),
                "predictions": predictions,
                "utilization_history": utilization_history,
                "tutors": tutors
            }

    except Exception as e:
        logger.error(f"Error getting subject detail for {subject}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve subject detail: {str(e)}"
        )

"""
Health Score API Endpoints

Provides REST API for customer health scores, churn risk detection,
and dashboard health metrics.
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.services.health_score_calculator import get_health_calculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["health"])


# Pydantic models for request/response validation


class HealthComponentsResponse(BaseModel):
    """Health score component breakdown"""
    first_session_success: float = Field(..., ge=0, le=100)
    session_velocity: float = Field(..., ge=0, le=100)
    ib_penalty: float = Field(..., ge=0, le=50)
    engagement_score: float = Field(..., ge=0, le=100)


class HealthMetricsDetail(BaseModel):
    """Detailed health metrics for a customer"""
    total_sessions: int = Field(..., ge=0)
    sessions_per_week: float = Field(..., ge=0)
    ib_calls_14_days: int = Field(..., ge=0)
    engagement_level: float = Field(..., ge=0, le=100)


class CustomerHealthResponse(BaseModel):
    """Response model for customer health score (AC-6)"""
    customer_id: str
    health_score: float = Field(..., ge=0, le=100)
    churn_risk: str = Field(..., pattern="^(low|medium|high)$")
    components: HealthComponentsResponse
    metrics: HealthMetricsDetail
    last_calculated: str


class HealthResponseData(BaseModel):
    """Wrapper for health response data"""
    data: CustomerHealthResponse
    metadata: Dict[str, Any]


class CohortHealthBreakdown(BaseModel):
    """Cohort-level health aggregates"""
    cohort_id: str
    avg_health_score: float = Field(..., ge=0, le=100)
    customer_count: int = Field(..., ge=0)
    churn_risk_high: int = Field(..., ge=0)


class DashboardHealthMetricsResponse(BaseModel):
    """Dashboard health metrics response (AC-8)"""
    total_customers: int = Field(..., ge=0)
    avg_health_score: float = Field(..., ge=0, le=100)
    health_distribution: Dict[str, int]
    churn_risk_counts: Dict[str, int]
    cohort_breakdown: List[CohortHealthBreakdown]


class DashboardMetricsData(BaseModel):
    """Wrapper for dashboard metrics data"""
    data: DashboardHealthMetricsResponse
    metadata: Dict[str, Any]


class RecalculateAllResponse(BaseModel):
    """Response for batch recalculation"""
    customers_processed: int
    health_scores_updated: int
    duration_ms: float
    timestamp: str


class RecalculateAllData(BaseModel):
    """Wrapper for recalculate all data"""
    data: RecalculateAllResponse


# API Endpoints


@router.get("/{customer_id}", response_model=HealthResponseData)
async def get_customer_health(
    customer_id: str = Path(..., description="Customer UUID as string")
) -> Dict[str, Any]:
    """
    Get current health score and churn risk for a customer (AC-6).

    Returns:
        - health_score: 0-100 score
        - churn_risk: low, medium, or high
        - components: breakdown of score components
        - metrics: detailed engagement metrics
        - last_calculated: ISO 8601 timestamp

    Raises:
        404: Customer not found or no data available
    """
    try:
        calculator = get_health_calculator()

        # Calculate health score
        health_score = await calculator.calculate_health_score(customer_id)

        # If score is 0, customer likely doesn't exist
        if health_score == 0:
            # Check if customer has any enrollments
            engagement = await calculator._get_engagement_score(customer_id)
            if engagement == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer '{customer_id}' not found or has no enrollment data"
                )

        # Get churn risk
        churn_risk = await calculator.detect_churn_risk(customer_id)

        # Get component breakdown
        first_session = await calculator._get_first_session_success(customer_id)
        velocity = await calculator._calculate_session_velocity(customer_id)
        ib_penalty = await calculator._calculate_ib_penalty(customer_id)
        engagement = await calculator._get_engagement_score(customer_id)

        # Calculate detailed metrics
        ib_calls = 0 if ib_penalty == 0 else (1 if ib_penalty == 20 else 2)
        sessions_per_week = (velocity / 100.0) * 5.0  # Reverse normalization

        response_data = {
            "customer_id": customer_id,
            "health_score": health_score,
            "churn_risk": churn_risk,
            "components": {
                "first_session_success": first_session,
                "session_velocity": velocity,
                "ib_penalty": ib_penalty,
                "engagement_score": engagement
            },
            "metrics": {
                "total_sessions": 0,  # TODO: Calculate from sessions table
                "sessions_per_week": round(sessions_per_week, 2),
                "ib_calls_14_days": ib_calls,
                "engagement_level": engagement
            },
            "last_calculated": "2025-11-08T14:35:00Z"  # TODO: Get from health_metrics table
        }

        return {
            "data": response_data,
            "metadata": {
                "timestamp": "2025-11-08T14:35:00Z",
                "cache_hit": False
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health for customer {customer_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate health score: {str(e)}"
        )


@router.get("/dashboard/metrics", response_model=DashboardMetricsData)
async def get_dashboard_health_metrics() -> Dict[str, Any]:
    """
    Get aggregated health metrics for dashboard overview (AC-8).

    Returns system-wide health aggregates including:
        - total_customers: Count of customers with recent health data
        - avg_health_score: Average health score across all customers
        - health_distribution: Count of customers by health level (high/medium/low)
        - churn_risk_counts: Count of customers by churn risk level
        - cohort_breakdown: Health aggregates per cohort

    Response time target: <500ms
    Cached for 5 minutes in production.
    """
    try:
        import time
        start_time = time.time()

        calculator = get_health_calculator()

        # Get dashboard metrics
        metrics = await calculator.get_dashboard_health_metrics()

        # Get cohort breakdown
        cohorts = await calculator.calculate_cohort_health_aggregates()

        calculation_time_ms = (time.time() - start_time) * 1000

        response_data = {
            "total_customers": metrics["total_customers"],
            "avg_health_score": metrics["avg_health_score"],
            "health_distribution": metrics["health_distribution"],
            "churn_risk_counts": metrics["churn_risk_counts"],
            "cohort_breakdown": cohorts
        }

        return {
            "data": response_data,
            "metadata": {
                "timestamp": "2025-11-08T14:35:00Z",
                "calculation_time_ms": round(calculation_time_ms, 2)
            }
        }

    except Exception as e:
        logger.error(f"Error getting dashboard health metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard metrics: {str(e)}"
        )


@router.post("/recalculate-all", response_model=RecalculateAllData)
async def recalculate_all_health_scores() -> Dict[str, Any]:
    """
    Admin endpoint to trigger batch recalculation of all customer health scores (AC-2).

    Calculates health scores for all active customers (enrollments in last 90 days).
    Performance target: <5 seconds for 500 customers.

    Returns:
        - customers_processed: Number of customers analyzed
        - health_scores_updated: Number of successful updates
        - duration_ms: Calculation duration in milliseconds
        - timestamp: ISO 8601 timestamp of completion

    Note: In production, this should be protected by authentication/authorization.
    """
    try:
        calculator = get_health_calculator()

        # Run batch calculation
        summary = await calculator.calculate_all_customers_health()

        return {"data": summary}

    except Exception as e:
        logger.error(f"Error in batch health recalculation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to recalculate health scores: {str(e)}"
        )

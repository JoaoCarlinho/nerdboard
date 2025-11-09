"""
Predictions API Endpoints

Provides REST API for retrieving ML predictions and explanations.
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


# Pydantic models

class PredictionSummary(BaseModel):
    """Summary prediction for list view"""
    prediction_id: str
    subject: str
    shortage_probability: float = Field(..., ge=0, le=1)
    predicted_shortage_date: Optional[str]
    days_until_shortage: int
    confidence_score: float = Field(..., ge=0, le=100)
    severity: str
    priority_score: float
    is_critical: bool
    created_at: str


class FeatureContribution(BaseModel):
    """SHAP feature contribution"""
    feature: str
    shap_value: float
    feature_value: float
    importance: float
    readable_description: str


class PredictionDetail(BaseModel):
    """Detailed prediction with explanation"""
    prediction_id: str
    subject: str
    shortage_probability: float
    predicted_shortage_date: Optional[str]
    days_until_shortage: int
    severity: str
    predicted_peak_utilization: float
    horizon: str
    horizon_days: int
    confidence_score: float
    confidence_level: str
    confidence_breakdown: Dict[str, float]
    priority_score: float
    is_critical: bool
    status: str
    created_at: str
    updated_at: str
    top_features: List[FeatureContribution]
    explanation_text: str


class PredictionsListResponse(BaseModel):
    """Paginated predictions list response"""
    predictions: List[PredictionSummary]
    meta: Dict[str, Any]


# API Endpoints

@router.get("", response_model=PredictionsListResponse)
async def get_predictions(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (critical, high, medium, low)"),
    horizon: Optional[str] = Query(None, description="Filter by horizon (2week, 4week, 6week, 8week)"),
    confidence_min: Optional[float] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    status: str = Query("active", description="Prediction status (active, resolved, expired)"),
    sort: str = Query("priority_desc", description="Sort by: priority_desc, priority_asc, date_desc, confidence_desc"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset")
) -> Dict[str, Any]:
    """
    Get list of predictions with filtering and sorting.

    Query parameters allow filtering by subject, urgency, horizon, and confidence.
    Results are paginated and sorted by priority by default.

    Response time target: <500ms
    """
    try:
        async with AsyncSessionLocal() as session:
            # Build WHERE clauses
            where_clauses = ["status = :status"]
            params = {"status": status, "limit": limit, "offset": offset}

            if subject:
                where_clauses.append("subject = :subject")
                params["subject"] = subject

            if horizon:
                where_clauses.append("horizon = :horizon")
                params["horizon"] = horizon

            if confidence_min is not None:
                where_clauses.append("confidence_score >= :confidence_min")
                params["confidence_min"] = confidence_min

            # Urgency mapping
            if urgency:
                if urgency == "critical":
                    where_clauses.append("is_critical = TRUE")
                elif urgency == "high":
                    where_clauses.append("priority_score >= 70")
                elif urgency == "medium":
                    where_clauses.append("priority_score >= 40 AND priority_score < 70")
                elif urgency == "low":
                    where_clauses.append("priority_score < 40")

            where_sql = " AND ".join(where_clauses)

            # Sort mapping
            sort_mapping = {
                "priority_desc": "priority_score DESC",
                "priority_asc": "priority_score ASC",
                "date_desc": "predicted_shortage_date DESC NULLS LAST",
                "confidence_desc": "confidence_score DESC"
            }
            order_by = sort_mapping.get(sort, "priority_score DESC")

            # Get total count
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM predictions
                WHERE {where_sql}
            """)
            count_result = await session.execute(count_query, params)
            total = count_result.fetchone().total

            # Get predictions
            query = text(f"""
                SELECT
                    prediction_id,
                    subject,
                    shortage_probability,
                    predicted_shortage_date,
                    days_until_shortage,
                    confidence_score,
                    severity,
                    priority_score,
                    is_critical,
                    created_at
                FROM predictions
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT :limit OFFSET :offset
            """)

            result = await session.execute(query, params)
            predictions = []

            for row in result.fetchall():
                predictions.append({
                    "prediction_id": row.prediction_id,
                    "subject": row.subject,
                    "shortage_probability": float(row.shortage_probability),
                    "predicted_shortage_date": row.predicted_shortage_date.isoformat() if row.predicted_shortage_date else None,
                    "days_until_shortage": row.days_until_shortage,
                    "confidence_score": float(row.confidence_score),
                    "severity": row.severity,
                    "priority_score": float(row.priority_score),
                    "is_critical": row.is_critical,
                    "created_at": row.created_at.isoformat()
                })

            return {
                "predictions": predictions,
                "meta": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "page": (offset // limit) + 1,
                    "pages": (total + limit - 1) // limit
                }
            }

    except Exception as e:
        logger.error(f"Error getting predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve predictions: {str(e)}"
        )


@router.get("/{prediction_id}", response_model=PredictionDetail)
async def get_prediction_detail(
    prediction_id: str = Path(..., description="Prediction ID")
) -> Dict[str, Any]:
    """
    Get detailed prediction with full explanation.

    Returns prediction data, confidence breakdown, SHAP features,
    and natural language explanation.

    Response time target: <500ms
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get prediction
            query = text("""
                SELECT
                    p.prediction_id,
                    p.subject,
                    p.shortage_probability,
                    p.predicted_shortage_date,
                    p.days_until_shortage,
                    p.severity,
                    p.predicted_peak_utilization,
                    p.horizon,
                    p.horizon_days,
                    p.confidence_score,
                    p.confidence_level,
                    p.confidence_breakdown,
                    p.priority_score,
                    p.is_critical,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    e.top_features,
                    e.explanation_text
                FROM predictions p
                LEFT JOIN explanations e ON p.prediction_id = e.prediction_id
                WHERE p.prediction_id = :prediction_id
            """)

            result = await session.execute(query, {"prediction_id": prediction_id})
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prediction {prediction_id} not found"
                )

            return {
                "prediction_id": row.prediction_id,
                "subject": row.subject,
                "shortage_probability": float(row.shortage_probability),
                "predicted_shortage_date": row.predicted_shortage_date.isoformat() if row.predicted_shortage_date else None,
                "days_until_shortage": row.days_until_shortage,
                "severity": row.severity,
                "predicted_peak_utilization": float(row.predicted_peak_utilization),
                "horizon": row.horizon,
                "horizon_days": row.horizon_days,
                "confidence_score": float(row.confidence_score),
                "confidence_level": row.confidence_level,
                "confidence_breakdown": row.confidence_breakdown,
                "priority_score": float(row.priority_score),
                "is_critical": row.is_critical,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "top_features": row.top_features if row.top_features else [],
                "explanation_text": row.explanation_text if row.explanation_text else ""
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prediction detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve prediction: {str(e)}"
        )


@router.get("/{prediction_id}/explanation")
async def get_prediction_explanation(
    prediction_id: str = Path(..., description="Prediction ID")
) -> Dict[str, Any]:
    """
    Get detailed explanation for a prediction.

    Returns SHAP feature contributions and natural language explanation separately.
    """
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT
                    top_features,
                    explanation_text,
                    historical_context,
                    created_at
                FROM explanations
                WHERE prediction_id = :prediction_id
            """)

            result = await session.execute(query, {"prediction_id": prediction_id})
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Explanation for prediction {prediction_id} not found"
                )

            return {
                "prediction_id": prediction_id,
                "top_features": row.top_features,
                "explanation_text": row.explanation_text,
                "historical_context": row.historical_context,
                "created_at": row.created_at.isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting explanation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve explanation: {str(e)}"
        )

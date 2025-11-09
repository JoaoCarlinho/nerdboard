"""
Data Quality Monitoring API Endpoints

Provides REST API for data quality scores, validation history, and issue tracking.
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.services.data_validator import get_data_validator
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


# Pydantic models


class ValidationIssue(BaseModel):
    """Individual validation issue"""
    rule: str
    type: str
    severity: str
    violations: int


class TableQualityStatus(BaseModel):
    """Quality status for a single table"""
    table_name: str
    quality_score: float = Field(..., ge=0, le=100)
    critical_issues: int = Field(..., ge=0)
    warnings: int = Field(..., ge=0)
    validation_time: str
    issues: List[ValidationIssue]


class QualityStatusResponse(BaseModel):
    """Overall quality status response"""
    validation_time: str
    tables_validated: int
    average_quality_score: float
    tables_below_threshold: int
    results: List[TableQualityStatus]


class QualityHistoryEntry(BaseModel):
    """Historical quality score entry"""
    validation_time: str
    quality_score: float
    critical_issues: int
    warnings: int


# API Endpoints


@router.get("/status", response_model=QualityStatusResponse)
async def get_quality_status() -> Dict[str, Any]:
    """
    Get current data quality scores for all tables.

    Returns quality scores, issue counts, and validation details
    for each monitored table.

    Response time target: <500ms
    """
    try:
        validator = get_data_validator()
        summary = await validator.validate_all_tables()

        return summary

    except Exception as e:
        logger.error(f"Error getting quality status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve quality status: {str(e)}"
        )


@router.get("/history/{table_name}")
async def get_quality_history(
    table_name: str = Path(..., description="Table name to get history for"),
    days: int = Query(7, ge=1, le=90, description="Number of days of history")
) -> Dict[str, Any]:
    """
    Get historical quality trends for a specific table.

    Shows quality score changes over time to identify degradation patterns.

    Args:
        table_name: Name of table to get history for
        days: Number of days of history (1-90, default 7)

    Returns:
        Historical quality scores and trend data
    """
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT
                    validation_time,
                    quality_score,
                    critical_issues,
                    warnings
                FROM data_quality_log
                WHERE table_name = :table_name
                AND validation_time >= NOW() - :days * INTERVAL '1 day'
                ORDER BY validation_time DESC
            """)
            result = await session.execute(query, {
                "table_name": table_name,
                "days": days
            })

            history = []
            for row in result.fetchall():
                history.append({
                    "validation_time": row.validation_time.isoformat(),
                    "quality_score": float(row.quality_score),
                    "critical_issues": row.critical_issues,
                    "warnings": row.warnings
                })

        if not history:
            return {
                "table_name": table_name,
                "days": days,
                "history": [],
                "message": f"No validation history found for table '{table_name}'"
            }

        # Calculate trend
        scores = [h["quality_score"] for h in history]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        trend = "improving" if len(scores) >= 2 and scores[0] > scores[-1] else \
                "declining" if len(scores) >= 2 and scores[0] < scores[-1] else "stable"

        return {
            "table_name": table_name,
            "days": days,
            "history": history,
            "summary": {
                "average_score": round(avg_score, 2),
                "latest_score": scores[0] if scores else 0.0,
                "trend": trend,
                "data_points": len(history)
            }
        }

    except Exception as e:
        logger.error(f"Error getting quality history for {table_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve quality history: {str(e)}"
        )


@router.get("/issues")
async def get_recent_issues(
    severity: str = Query(None, description="Filter by severity (critical, warning)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of issues to return")
) -> Dict[str, Any]:
    """
    Get recent validation failures and issues.

    Useful for debugging and monitoring data quality problems.

    Args:
        severity: Optional filter by severity level
        limit: Maximum number of issues (1-500, default 50)

    Returns:
        Recent validation issues with details
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get recent validation logs with issues
            query = text("""
                SELECT
                    table_name,
                    validation_time,
                    quality_score,
                    critical_issues,
                    warnings,
                    issues_json
                FROM data_quality_log
                WHERE (critical_issues > 0 OR warnings > 0)
                ORDER BY validation_time DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"limit": limit})

            issues_list = []
            for row in result.fetchall():
                # Filter by severity if specified
                if severity:
                    # This is simplified - in production would filter JSON issues
                    if severity == "critical" and row.critical_issues == 0:
                        continue
                    if severity == "warning" and row.warnings == 0:
                        continue

                issues_list.append({
                    "table_name": row.table_name,
                    "validation_time": row.validation_time.isoformat(),
                    "quality_score": float(row.quality_score),
                    "critical_issues": row.critical_issues,
                    "warnings": row.warnings,
                    "issues": row.issues_json.get("issues", []) if row.issues_json else []
                })

        return {
            "issues_count": len(issues_list),
            "severity_filter": severity,
            "issues": issues_list
        }

    except Exception as e:
        logger.error(f"Error getting recent issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve issues: {str(e)}"
        )


@router.post("/validate/{table_name}")
async def trigger_validation(
    table_name: str = Path(..., description="Table name to validate")
) -> Dict[str, Any]:
    """
    Manually trigger validation for a specific table.

    Useful for on-demand quality checks after data updates.

    Args:
        table_name: Name of table to validate

    Returns:
        Validation results
    """
    try:
        validator = get_data_validator()
        result = await validator.validate_table(table_name)

        return {
            "status": "validation_complete",
            "result": result
        }

    except Exception as e:
        logger.error(f"Error triggering validation for {table_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate table: {str(e)}"
        )

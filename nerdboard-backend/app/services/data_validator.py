"""
Data Quality Validator

Validates data integrity, detects anomalies, and calculates quality scores
per data stream. Alerts when quality drops below acceptable thresholds.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from sqlalchemy import text
import statistics

from app.database import AsyncSessionLocal
from app.models.data_quality_log import DataQualityLog

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate data quality and detect anomalies"""

    # Quality score thresholds
    ALERT_THRESHOLD = 80.0  # Alert when quality drops below 80%
    CRITICAL_ERROR_WEIGHT = 20.0  # Critical errors reduce score by 20% each
    WARNING_WEIGHT = 5.0  # Warnings reduce score by 5% each

    # Anomaly detection parameters
    ANOMALY_STD_THRESHOLD = 3.0  # Flag if >3 standard deviations from mean
    ROLLING_WINDOW_DAYS = 7  # Use 7-day rolling average

    def __init__(self):
        """Initialize data validator"""
        self.validation_rules = self._define_validation_rules()

    def _define_validation_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Define validation rules for each table (AC-1, AC-2).

        Returns:
            dict: Validation rules per table
        """
        return {
            "enrollments": [
                {
                    "name": "student_id_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM enrollments WHERE student_id IS NULL"
                },
                {
                    "name": "subject_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM enrollments WHERE subject IS NULL"
                },
                {
                    "name": "engagement_score_range",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM enrollments WHERE engagement_score < 0 OR engagement_score > 1"
                },
                {
                    "name": "future_start_date",
                    "type": "anomaly",
                    "severity": "warning",
                    "query": "SELECT COUNT(*) FROM enrollments WHERE start_date > NOW()"
                }
            ],
            "tutors": [
                {
                    "name": "tutor_id_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM tutors WHERE tutor_id IS NULL"
                },
                {
                    "name": "subjects_not_empty",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM tutors WHERE subjects IS NULL OR cardinality(subjects) = 0"
                },
                {
                    "name": "weekly_capacity_range",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM tutors WHERE weekly_capacity_hours <= 0 OR weekly_capacity_hours > 168"
                },
                {
                    "name": "utilization_rate_range",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM tutors WHERE utilization_rate < 0 OR utilization_rate > 1"
                }
            ],
            "sessions": [
                {
                    "name": "session_id_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM sessions WHERE session_id IS NULL"
                },
                {
                    "name": "student_id_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM sessions WHERE student_id IS NULL"
                },
                {
                    "name": "duration_positive",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM sessions WHERE duration_minutes <= 0"
                },
                {
                    "name": "tutor_foreign_key",
                    "type": "integrity",
                    "severity": "warning",
                    "query": """
                        SELECT COUNT(*) FROM sessions s
                        WHERE s.tutor_id IS NOT NULL
                        AND NOT EXISTS (SELECT 1 FROM tutors t WHERE t.id = s.tutor_id)
                    """
                }
            ],
            "health_metrics": [
                {
                    "name": "customer_id_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM health_metrics WHERE customer_id IS NULL"
                },
                {
                    "name": "health_score_range",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM health_metrics WHERE health_score < 0 OR health_score > 100"
                },
                {
                    "name": "future_date",
                    "type": "anomaly",
                    "severity": "warning",
                    "query": "SELECT COUNT(*) FROM health_metrics WHERE date > NOW()"
                }
            ],
            "capacity_snapshots": [
                {
                    "name": "subject_not_null",
                    "type": "integrity",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM capacity_snapshots WHERE subject IS NULL"
                },
                {
                    "name": "utilization_rate_range",
                    "type": "range",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM capacity_snapshots WHERE utilization_rate < 0"
                },
                {
                    "name": "negative_hours",
                    "type": "anomaly",
                    "severity": "critical",
                    "query": "SELECT COUNT(*) FROM capacity_snapshots WHERE total_hours < 0 OR booked_hours < 0"
                }
            ]
        }

    async def validate_table(self, table_name: str) -> Dict[str, Any]:
        """
        Validate a single table against all defined rules (AC-1, AC-2).

        Args:
            table_name: Name of table to validate

        Returns:
            dict: Validation results with quality score and issues
        """
        if table_name not in self.validation_rules:
            return {
                "table_name": table_name,
                "quality_score": 0.0,
                "validation_time": datetime.utcnow().isoformat(),
                "issues": [{"error": f"No validation rules defined for table '{table_name}'"}]
            }

        async with AsyncSessionLocal() as session:
            issues = []
            critical_count = 0
            warning_count = 0

            # Run all validation rules
            for rule in self.validation_rules[table_name]:
                try:
                    result = await session.execute(text(rule["query"]))
                    violation_count = result.scalar() or 0

                    if violation_count > 0:
                        issue = {
                            "rule": rule["name"],
                            "type": rule["type"],
                            "severity": rule["severity"],
                            "violations": violation_count
                        }
                        issues.append(issue)

                        if rule["severity"] == "critical":
                            critical_count += 1
                        else:
                            warning_count += 1

                except Exception as e:
                    logger.error(f"Error running validation rule {rule['name']}: {e}")
                    issues.append({
                        "rule": rule["name"],
                        "error": str(e)
                    })

        # Calculate quality score (AC-3)
        quality_score = self._calculate_quality_score(critical_count, warning_count)

        return {
            "table_name": table_name,
            "quality_score": quality_score,
            "validation_time": datetime.utcnow().isoformat(),
            "critical_issues": critical_count,
            "warnings": warning_count,
            "issues": issues
        }

    def _calculate_quality_score(self, critical_count: int, warning_count: int) -> float:
        """
        Calculate quality score (0-100%) based on issues (AC-3).

        Formula: 100 - (critical * 20 + warnings * 5)

        Args:
            critical_count: Number of critical issues
            warning_count: Number of warnings

        Returns:
            float: Quality score 0-100
        """
        score = 100.0 - (
            critical_count * self.CRITICAL_ERROR_WEIGHT +
            warning_count * self.WARNING_WEIGHT
        )

        return max(0.0, min(100.0, score))  # Clamp to 0-100

    async def validate_all_tables(self) -> Dict[str, Any]:
        """
        Validate all tables and return summary (AC-3, AC-4).

        Returns:
            dict: Validation summary with overall quality
        """
        tables = list(self.validation_rules.keys())
        results = []
        total_quality = 0.0

        for table in tables:
            table_result = await self.validate_table(table)
            results.append(table_result)
            total_quality += table_result["quality_score"]

            # Alert if quality below threshold (AC-4)
            if table_result["quality_score"] < self.ALERT_THRESHOLD:
                logger.warning(
                    f"Data quality ALERT: {table} score {table_result['quality_score']:.1f}% "
                    f"(threshold: {self.ALERT_THRESHOLD}%)"
                )

            # Save to database (AC-5)
            await self.save_validation_result(table_result)

        avg_quality = total_quality / len(tables) if tables else 0.0

        return {
            "validation_time": datetime.utcnow().isoformat(),
            "tables_validated": len(tables),
            "average_quality_score": round(avg_quality, 2),
            "tables_below_threshold": sum(1 for r in results if r["quality_score"] < self.ALERT_THRESHOLD),
            "results": results
        }

    async def save_validation_result(self, result: Dict[str, Any]) -> None:
        """
        Save validation result to data_quality_log table (AC-5).

        Args:
            result: Validation result from validate_table()
        """
        async with AsyncSessionLocal() as session:
            quality_log = DataQualityLog(
                table_name=result["table_name"],
                validation_time=datetime.utcnow(),
                quality_score=result["quality_score"],
                critical_issues=result.get("critical_issues", 0),
                warnings=result.get("warnings", 0),
                issues_json={"issues": result.get("issues", [])}
            )
            session.add(quality_log)
            await session.commit()

    async def detect_anomalies(self, table_name: str, metric_name: str) -> List[Dict[str, Any]]:
        """
        Detect anomalies using 7-day rolling average and std deviation (AC-2).

        Flags values >3 standard deviations from rolling mean.

        Args:
            table_name: Table to check
            metric_name: Metric to analyze (e.g., 'count', 'avg_value')

        Returns:
            list: Detected anomalies
        """
        # This is a simplified implementation
        # In production, would query time-series data and analyze trends

        anomalies = []

        # Example: Detect enrollment count spikes
        if table_name == "enrollments":
            async with AsyncSessionLocal() as session:
                # Get daily counts for last 14 days
                query = text("""
                    SELECT DATE(start_date) as date, COUNT(*) as count
                    FROM enrollments
                    WHERE start_date >= NOW() - INTERVAL '14 days'
                    GROUP BY DATE(start_date)
                    ORDER BY date
                """)
                result = await session.execute(query)
                daily_counts = [(row.date, row.count) for row in result.fetchall()]

                if len(daily_counts) >= 7:
                    # Calculate rolling statistics
                    counts = [count for _, count in daily_counts]
                    rolling_mean = statistics.mean(counts[-7:])
                    rolling_std = statistics.stdev(counts[-7:]) if len(counts[-7:]) > 1 else 0

                    # Check most recent day for anomaly
                    if rolling_std > 0:
                        latest_count = counts[-1]
                        z_score = abs(latest_count - rolling_mean) / rolling_std

                        if z_score > self.ANOMALY_STD_THRESHOLD:
                            anomalies.append({
                                "table": table_name,
                                "metric": "daily_enrollments",
                                "value": latest_count,
                                "expected_range": f"{rolling_mean - 3*rolling_std:.0f}-{rolling_mean + 3*rolling_std:.0f}",
                                "z_score": round(z_score, 2),
                                "severity": "high" if z_score > 5 else "medium"
                            })

        return anomalies


# Singleton instance
_data_validator_instance = None


def get_data_validator() -> DataValidator:
    """Get singleton instance of DataValidator"""
    global _data_validator_instance
    if _data_validator_instance is None:
        _data_validator_instance = DataValidator()
    return _data_validator_instance

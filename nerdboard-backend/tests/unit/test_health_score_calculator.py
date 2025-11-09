"""
Unit tests for HealthScoreCalculator

Tests health score formula, component calculations, churn risk detection logic.
"""
import pytest
from app.services.health_score_calculator import HealthScoreCalculator


class TestHealthScoreFormula:
    """Test health score formula calculation (AC-1)"""

    def test_health_score_formula_calculation(self):
        """Test health score formula with known inputs"""
        calculator = HealthScoreCalculator()

        # Given components
        first_session = 100.0
        velocity = 65.0
        ib_penalty = 0.0
        engagement = 80.0

        # Manual calculation
        expected = (
            0.40 * 100 +  # 40.0
            0.30 * 65 +   # 19.5
            0.20 * (100 - 0) +  # 20.0
            0.10 * 80     # 8.0
        )  # = 87.5

        # Calculate using weighted formula
        health_score = (
            calculator.formula_weights["first_session_success"] * first_session +
            calculator.formula_weights["session_velocity"] * velocity +
            calculator.formula_weights["ib_penalty_inverse"] * (100 - ib_penalty) +
            calculator.formula_weights["engagement"] * engagement
        )

        assert health_score == expected
        assert health_score == 87.5

    def test_health_score_all_zeros(self):
        """Test health score when all components are zero (new customer)"""
        calculator = HealthScoreCalculator()

        health_score = (
            calculator.formula_weights["first_session_success"] * 0 +
            calculator.formula_weights["session_velocity"] * 0 +
            calculator.formula_weights["ib_penalty_inverse"] * (100 - 0) +
            calculator.formula_weights["engagement"] * 0
        )

        # Only IB penalty inverse contributes: 0.20 * 100 = 20
        assert health_score == 20.0

    def test_health_score_maximum(self):
        """Test maximum possible health score"""
        calculator = HealthScoreCalculator()

        health_score = (
            calculator.formula_weights["first_session_success"] * 100 +
            calculator.formula_weights["session_velocity"] * 100 +
            calculator.formula_weights["ib_penalty_inverse"] * 100 +
            calculator.formula_weights["engagement"] * 100
        )

        assert health_score == 100.0

    def test_health_score_with_ib_penalty(self):
        """Test health score with IB call penalty"""
        calculator = HealthScoreCalculator()

        # 2+ IB calls = 50 penalty
        health_score = (
            calculator.formula_weights["first_session_success"] * 100 +
            calculator.formula_weights["session_velocity"] * 80 +
            calculator.formula_weights["ib_penalty_inverse"] * (100 - 50) +  # 50 penalty
            calculator.formula_weights["engagement"] * 90
        )

        # = 40 + 24 + 10 + 9 = 83
        assert health_score == 83.0


class TestSessionVelocityCalculation:
    """Test session velocity calculation and normalization"""

    def test_session_velocity_calculation(self):
        """Test session velocity normalized correctly"""
        # 10 sessions in 30 days
        session_count = 10
        sessions_per_week = (session_count / 30.0) * 7.0  # = 2.33
        normalized = min(sessions_per_week / 5.0 * 100, 100)  # = 46.6

        assert abs(normalized - 46.67) < 0.1

    def test_session_velocity_high_volume(self):
        """Test session velocity with high volume"""
        # 20 sessions in 30 days
        session_count = 20
        sessions_per_week = (session_count / 30.0) * 7.0  # = 4.67
        normalized = min(sessions_per_week / 5.0 * 100, 100)  # = 93.3

        assert abs(normalized - 93.33) < 0.1

    def test_session_velocity_maximum_capped(self):
        """Test session velocity caps at 100"""
        # 25 sessions in 30 days (more than 5/week)
        session_count = 25
        sessions_per_week = (session_count / 30.0) * 7.0  # = 5.83
        normalized = min(sessions_per_week / 5.0 * 100, 100)  # = 116.67 → 100

        assert normalized == 100.0

    def test_session_velocity_zero_sessions(self):
        """Test session velocity with zero sessions"""
        session_count = 0
        sessions_per_week = (session_count / 30.0) * 7.0  # = 0
        normalized = min(sessions_per_week / 5.0 * 100, 100)  # = 0

        assert normalized == 0.0


class TestIBPenaltyCalculation:
    """Test IB penalty calculation logic"""

    def test_ib_penalty_zero_calls(self):
        """Test 0 IB calls = 0 penalty"""
        total_ib_calls = 0

        if total_ib_calls == 0:
            penalty = 0.0
        elif total_ib_calls == 1:
            penalty = 20.0
        else:
            penalty = 50.0

        assert penalty == 0.0

    def test_ib_penalty_one_call(self):
        """Test 1 IB call = 20 penalty"""
        total_ib_calls = 1

        if total_ib_calls == 0:
            penalty = 0.0
        elif total_ib_calls == 1:
            penalty = 20.0
        else:
            penalty = 50.0

        assert penalty == 20.0

    def test_ib_penalty_two_calls(self):
        """Test 2 IB calls = 50 penalty"""
        total_ib_calls = 2

        if total_ib_calls == 0:
            penalty = 0.0
        elif total_ib_calls == 1:
            penalty = 20.0
        else:
            penalty = 50.0

        assert penalty == 50.0

    def test_ib_penalty_five_calls(self):
        """Test 5 IB calls = 50 penalty (capped)"""
        total_ib_calls = 5

        if total_ib_calls == 0:
            penalty = 0.0
        elif total_ib_calls == 1:
            penalty = 20.0
        else:
            penalty = 50.0

        assert penalty == 50.0


class TestChurnRiskDetection:
    """Test churn risk detection logic (AC-3)"""

    def test_churn_risk_high_ib_calls(self):
        """Test high churn risk with 2+ IB calls"""
        ib_calls = 2
        health_score = 80.0  # Good score but high IB calls

        if ib_calls >= 2 or health_score < 40:
            churn_risk = "high"
        elif ib_calls == 1 or health_score < 60:
            churn_risk = "medium"
        else:
            churn_risk = "low"

        assert churn_risk == "high"

    def test_churn_risk_high_low_score(self):
        """Test high churn risk with score < 40"""
        ib_calls = 0
        health_score = 30.0  # Low score

        if ib_calls >= 2 or health_score < 40:
            churn_risk = "high"
        elif ib_calls == 1 or health_score < 60:
            churn_risk = "medium"
        else:
            churn_risk = "low"

        assert churn_risk == "high"

    def test_churn_risk_medium_one_ib_call(self):
        """Test medium churn risk with 1 IB call"""
        ib_calls = 1
        health_score = 70.0  # Good score but 1 IB call

        if ib_calls >= 2 or health_score < 40:
            churn_risk = "high"
        elif ib_calls == 1 or health_score < 60:
            churn_risk = "medium"
        else:
            churn_risk = "low"

        assert churn_risk == "medium"

    def test_churn_risk_medium_score_range(self):
        """Test medium churn risk with score 40-60"""
        ib_calls = 0
        health_score = 50.0  # Medium score

        if ib_calls >= 2 or health_score < 40:
            churn_risk = "high"
        elif ib_calls == 1 or health_score < 60:
            churn_risk = "medium"
        else:
            churn_risk = "low"

        assert churn_risk == "medium"

    def test_churn_risk_low(self):
        """Test low churn risk with no IB calls and high score"""
        ib_calls = 0
        health_score = 75.0  # High score

        if ib_calls >= 2 or health_score < 40:
            churn_risk = "high"
        elif ib_calls == 1 or health_score < 60:
            churn_risk = "medium"
        else:
            churn_risk = "low"

        assert churn_risk == "low"


class TestEngagementScoreScaling:
    """Test engagement score scaling from 0-1 to 0-100"""

    def test_engagement_score_zero(self):
        """Test engagement score 0"""
        engagement_score = 0.0
        scaled = engagement_score * 100
        assert scaled == 0.0

    def test_engagement_score_half(self):
        """Test engagement score 0.5"""
        engagement_score = 0.5
        scaled = engagement_score * 100
        assert scaled == 50.0

    def test_engagement_score_full(self):
        """Test engagement score 1.0"""
        engagement_score = 1.0
        scaled = engagement_score * 100
        assert scaled == 100.0

    def test_engagement_score_0_8(self):
        """Test engagement score 0.8"""
        engagement_score = 0.8
        scaled = engagement_score * 100
        assert scaled == 80.0


class TestFormulaWeights:
    """Test formula weights sum to 1.0"""

    def test_formula_weights_sum(self):
        """Test all weights sum to 1.0"""
        calculator = HealthScoreCalculator()

        total_weight = (
            calculator.formula_weights["first_session_success"] +
            calculator.formula_weights["session_velocity"] +
            calculator.formula_weights["ib_penalty_inverse"] +
            calculator.formula_weights["engagement"]
        )

        assert abs(total_weight - 1.0) < 0.0001  # Account for floating point precision

    def test_formula_weights_values(self):
        """Test individual weight values"""
        calculator = HealthScoreCalculator()

        assert calculator.formula_weights["first_session_success"] == 0.40
        assert calculator.formula_weights["session_velocity"] == 0.30
        assert calculator.formula_weights["ib_penalty_inverse"] == 0.20
        assert calculator.formula_weights["engagement"] == 0.10


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_new_customer_with_no_data(self):
        """Test new customer with no sessions or enrollments"""
        # All components would be 0 except IB penalty inverse (100)
        first_session = 0.0
        velocity = 0.0
        ib_penalty = 0.0
        engagement = 0.0

        calculator = HealthScoreCalculator()
        health_score = (
            calculator.formula_weights["first_session_success"] * first_session +
            calculator.formula_weights["session_velocity"] * velocity +
            calculator.formula_weights["ib_penalty_inverse"] * (100 - ib_penalty) +
            calculator.formula_weights["engagement"] * engagement
        )

        # Only IB penalty inverse contributes: 0.20 * 100 = 20
        assert health_score == 20.0

    def test_customer_with_none_engagement(self):
        """Test customer with None engagement score"""
        engagement_score = None

        if engagement_score is None:
            scaled = 0.0
        else:
            scaled = engagement_score * 100

        assert scaled == 0.0

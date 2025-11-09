-- Migration: Add predictions and explanations tables
-- Story: 2.2, 2.3, 2.4, 2.5 Prediction Engine
-- Date: 2025-11-08

-- Predictions table
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    prediction_id VARCHAR(50) UNIQUE NOT NULL,
    subject VARCHAR(100) NOT NULL,

    -- Prediction outputs
    shortage_probability FLOAT NOT NULL,
    predicted_shortage_date TIMESTAMP,
    days_until_shortage INTEGER,
    severity VARCHAR(20),  -- low, medium, high
    predicted_peak_utilization FLOAT,

    -- Prediction metadata
    horizon VARCHAR(20) NOT NULL,  -- 2week, 4week, 6week, 8week
    horizon_days INTEGER NOT NULL,

    -- Confidence scoring
    confidence_score FLOAT NOT NULL,
    confidence_level VARCHAR(20),  -- low, medium, high
    confidence_breakdown JSONB,

    -- Prioritization
    priority_score FLOAT,
    is_critical BOOLEAN DEFAULT FALSE,

    -- Status
    status VARCHAR(20) DEFAULT 'active',  -- active, resolved, expired

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT check_probability CHECK (shortage_probability >= 0 AND shortage_probability <= 1),
    CONSTRAINT check_confidence CHECK (confidence_score >= 0 AND confidence_score <= 100)
);

-- Explanations table
CREATE TABLE IF NOT EXISTS explanations (
    id SERIAL PRIMARY KEY,
    prediction_id VARCHAR(50) NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,

    -- SHAP values and feature importance
    top_features JSONB,  -- Array of {feature, shap_value, readable_description}

    -- Natural language explanation
    explanation_text TEXT NOT NULL,

    -- Historical context
    historical_context TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_prediction_explanation UNIQUE (prediction_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_predictions_subject ON predictions(subject);
CREATE INDEX IF NOT EXISTS idx_predictions_shortage_date ON predictions(predicted_shortage_date);
CREATE INDEX IF NOT EXISTS idx_predictions_priority ON predictions(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_critical ON predictions(is_critical) WHERE is_critical = TRUE;

CREATE INDEX IF NOT EXISTS idx_explanations_prediction ON explanations(prediction_id);

-- Comments
COMMENT ON TABLE predictions IS 'ML model predictions for capacity shortages';
COMMENT ON TABLE explanations IS 'Explainability data (SHAP values and natural language) for predictions';

COMMENT ON COLUMN predictions.shortage_probability IS 'ML model probability of shortage (0-1)';
COMMENT ON COLUMN predictions.confidence_score IS 'Confidence in prediction (0-100)';
COMMENT ON COLUMN predictions.confidence_breakdown IS 'JSON breakdown of confidence components';
COMMENT ON COLUMN predictions.priority_score IS 'Urgency × confidence × severity (0-100)';
COMMENT ON COLUMN predictions.is_critical IS 'TRUE if <14 days AND >70% confidence AND severity>30%';

COMMENT ON COLUMN explanations.top_features IS 'Top 5 contributing features with SHAP values';
COMMENT ON COLUMN explanations.explanation_text IS 'Human-readable explanation of prediction';

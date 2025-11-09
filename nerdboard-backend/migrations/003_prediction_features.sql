-- Migration: Add prediction_features table
-- Story: 2.1 Feature Engineering Pipeline
-- Date: 2025-11-08

CREATE TABLE IF NOT EXISTS prediction_features (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(100) NOT NULL,
    reference_date TIMESTAMP NOT NULL,
    features_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_subject_reference_date UNIQUE (subject, reference_date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prediction_features_subject ON prediction_features(subject);
CREATE INDEX IF NOT EXISTS idx_prediction_features_reference_date ON prediction_features(reference_date);
CREATE INDEX IF NOT EXISTS idx_prediction_features_created_at ON prediction_features(created_at DESC);

COMMENT ON TABLE prediction_features IS 'Stores extracted time-series features for ML model input';
COMMENT ON COLUMN prediction_features.subject IS 'Subject name (e.g., Physics, SAT Prep)';
COMMENT ON COLUMN prediction_features.reference_date IS 'Date when features were extracted for';
COMMENT ON COLUMN prediction_features.features_json IS 'JSON object containing all extracted features';
COMMENT ON COLUMN prediction_features.created_at IS 'Timestamp when features were extracted';

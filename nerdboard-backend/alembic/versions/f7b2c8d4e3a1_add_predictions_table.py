"""add predictions table

Revision ID: f7b2c8d4e3a1
Revises: e43725e01c4c
Create Date: 2025-11-10 01:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f7b2c8d4e3a1'
down_revision: Union[str, None] = 'e43725e01c4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create predictions table
    op.create_table('predictions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('prediction_id', sa.String(length=100), nullable=False),
    sa.Column('subject', sa.String(length=100), nullable=False),
    sa.Column('shortage_probability', sa.Float(), nullable=False),
    sa.Column('predicted_shortage_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('days_until_shortage', sa.Integer(), nullable=False),
    sa.Column('predicted_peak_utilization', sa.Float(), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('confidence_level', sa.String(length=20), nullable=True),
    sa.Column('confidence_breakdown', sa.Text(), nullable=True),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('priority_score', sa.Float(), nullable=False),
    sa.Column('is_critical', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('horizon', sa.String(length=20), nullable=True),
    sa.Column('horizon_days', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
    sa.Column('explanation_text', sa.Text(), nullable=True),
    sa.Column('shap_values', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('prediction_id')
    )

    # Create indexes for performance
    op.create_index('idx_predictions_prediction_id', 'predictions', ['prediction_id'], unique=False)
    op.create_index('idx_predictions_subject', 'predictions', ['subject'], unique=False)
    op.create_index('idx_predictions_status', 'predictions', ['status'], unique=False)
    op.create_index('idx_predictions_priority', 'predictions', ['priority_score'], unique=False)
    op.create_index('idx_predictions_created_at', 'predictions', ['created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_predictions_created_at', table_name='predictions', postgresql_ops={'created_at': 'DESC'})
    op.drop_index('idx_predictions_priority', table_name='predictions')
    op.drop_index('idx_predictions_status', table_name='predictions')
    op.drop_index('idx_predictions_subject', table_name='predictions')
    op.drop_index('idx_predictions_prediction_id', table_name='predictions')

    # Drop table
    op.drop_table('predictions')

"""Initial NexusID schema

Revision ID: 0001
Revises: None
Create Date: 2024-12-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('business_records',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('source_system', sa.String(), nullable=False),
        sa.Column('source_record_id', sa.String(), nullable=False),
        sa.Column('business_name', sa.String(), nullable=False),
        sa.Column('address_line', sa.String(), default=''),
        sa.Column('address_locality', sa.String(), default=''),
        sa.Column('address_city', sa.String(), default=''),
        sa.Column('address_district', sa.String(), default=''),
        sa.Column('address_pincode', sa.String(), default=''),
        sa.Column('address_state', sa.String(), default='Karnataka'),
        sa.Column('pan', sa.String(), nullable=True),
        sa.Column('gstin', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('registration_date', sa.Date(), nullable=True),
        sa.Column('registration_type', sa.String(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('ingested_at', sa.DateTime()),
        sa.Column('gt_id', sa.String(), nullable=True),
        sa.UniqueConstraint('source_system', 'source_record_id', name='uq_source_record'),
    )
    op.create_index('ix_content_hash', 'business_records', ['content_hash'])
    op.create_index('ix_pan', 'business_records', ['pan'])
    op.create_index('ix_gstin', 'business_records', ['gstin'])

    op.create_table('ubid_master',
        sa.Column('ubid', sa.String(), primary_key=True),
        sa.Column('anchor_type', sa.String(), nullable=False),
        sa.Column('anchor_value', sa.String(), nullable=True),
        sa.Column('primary_name', sa.String(), nullable=True),
        sa.Column('primary_address', sa.String(), nullable=True),
        sa.Column('primary_pincode', sa.String(), nullable=True),
        sa.Column('primary_district', sa.String(), nullable=True),
        sa.Column('status', sa.String(), default='ACTIVE'),
        sa.Column('deprecated_by_ubid', sa.String(), sa.ForeignKey('ubid_master.ubid'), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table('ubid_source_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ubid', sa.String(), sa.ForeignKey('ubid_master.ubid'), nullable=False),
        sa.Column('source_system', sa.String(), nullable=False),
        sa.Column('source_record_id', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('joined_at', sa.DateTime()),
        sa.UniqueConstraint('source_system', 'source_record_id', name='uq_ubid_source'),
    )

    op.create_table('merge_provenance',
        sa.Column('merge_id', sa.String(), primary_key=True),
        sa.Column('ubid_winner', sa.String(), sa.ForeignKey('ubid_master.ubid'), nullable=False),
        sa.Column('ubid_loser', sa.String(), sa.ForeignKey('ubid_master.ubid'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('decided_by', sa.String(), default='SYSTEM'),
        sa.Column('decided_at', sa.DateTime()),
        sa.Column('feature_breakdown', sa.JSON(), nullable=True),
        sa.Column('reversed', sa.Boolean(), default=False),
    )

    op.create_table('merge_reversals',
        sa.Column('reversal_id', sa.String(), primary_key=True),
        sa.Column('merge_id', sa.String(), sa.ForeignKey('merge_provenance.merge_id'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('reversed_by', sa.String(), nullable=False),
        sa.Column('reversed_at', sa.DateTime()),
    )

    op.create_table('candidate_pairs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('record_a_id', sa.String(), sa.ForeignKey('business_records.id'), nullable=False),
        sa.Column('record_b_id', sa.String(), sa.ForeignKey('business_records.id'), nullable=False),
        sa.Column('blocking_keys', sa.JSON(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('decision', sa.String(), nullable=True),
        sa.Column('feature_breakdown', sa.JSON(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('review_status', sa.String(), default='PENDING'),
        sa.Column('reviewer_id', sa.String(), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table('activity_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ubid', sa.String(), sa.ForeignKey('ubid_master.ubid'), nullable=True),
        sa.Column('source_system', sa.String(), nullable=False),
        sa.Column('source_event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('signal_class', sa.String(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('ingested_at', sa.DateTime()),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
    )

    op.create_table('activity_status_current',
        sa.Column('ubid', sa.String(), sa.ForeignKey('ubid_master.ubid'), primary_key=True),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('score', sa.Float(), server_default='0'),
        sa.Column('last_strong_active_at', sa.DateTime(), nullable=True),
        sa.Column('status_since', sa.DateTime()),
        sa.Column('last_recomputed_at', sa.DateTime()),
        sa.Column('event_count', sa.Integer(), server_default='0'),
        sa.Column('last_event_date', sa.Date(), nullable=True),
    )

    op.create_table('event_ledger',
        sa.Column('ledger_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('aggregate_type', sa.String(), nullable=False),
        sa.Column('aggregate_id', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('prev_hash', sa.String(), nullable=False),
        sa.Column('hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_ledger_aggregate', 'event_ledger', ['aggregate_id'])

    op.create_table('query_audit',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('query_type', sa.String(), nullable=False),
        sa.Column('query_params', sa.JSON(), nullable=True),
        sa.Column('result_count', sa.Integer(), server_default='0'),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('executed_at', sa.DateTime()),
    )

    op.create_table('adapter_health',
        sa.Column('source_system', sa.String(), primary_key=True),
        sa.Column('last_successful_pull_at', sa.DateTime(), nullable=True),
        sa.Column('last_record_count', sa.Integer(), server_default='0'),
        sa.Column('total_records', sa.Integer(), server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('freshness_seconds', sa.Float(), server_default='0'),
        sa.Column('status', sa.String(), server_default='HEALTHY'),
        sa.Column('updated_at', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('adapter_health')
    op.drop_table('query_audit')
    op.drop_table('event_ledger')
    op.drop_table('activity_status_current')
    op.drop_table('activity_events')
    op.drop_table('candidate_pairs')
    op.drop_table('merge_reversals')
    op.drop_table('merge_provenance')
    op.drop_table('ubid_source_records')
    op.drop_table('ubid_master')
    op.drop_table('business_records')

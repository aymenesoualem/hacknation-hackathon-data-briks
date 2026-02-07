"""init

Revision ID: 0001
Revises:
Create Date: 2026-02-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("district", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("source_row_id", sa.String(), nullable=True),
        sa.Column("raw_structured_json", sa.JSON(), nullable=True),
        sa.Column("raw_text_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("extracted_json", sa.JSON(), nullable=False),
        sa.Column("confidence_json", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "evidence_spans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("extraction_id", sa.Integer(), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("source_row_id", sa.String(), nullable=True),
        sa.Column("source_field", sa.String(), nullable=False),
        sa.Column("quote", sa.String(), nullable=False),
        sa.Column("supports_path", sa.String(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("evidence_span_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trace_type", sa.String(), nullable=False),
        sa.Column("trace_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "planner_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_text", sa.String(), nullable=False),
        sa.Column("answer_text", sa.String(), nullable=False),
        sa.Column("answer_json", sa.JSON(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.Integer(), sa.ForeignKey("agent_traces.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("planner_queries")
    op.drop_table("agent_traces")
    op.drop_table("anomalies")
    op.drop_table("evidence_spans")
    op.drop_table("extractions")
    op.drop_table("facilities")

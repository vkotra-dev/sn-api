"""layout upload jobs

Revision ID: 0002_layout_upload_jobs
Revises: 0001_initial_schema
Create Date: 2026-05-20 00:00:01
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_layout_upload_jobs"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "layout_upload_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("layout_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("source_dxf_key", sa.Text(), nullable=False),
        sa.Column("source_excel_key", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["layout_id"], ["layouts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("layout_id"),
    )
    op.create_index("idx_layout_upload_jobs_layout_id", "layout_upload_jobs", ["layout_id"], unique=False)
    op.create_index("idx_layout_upload_jobs_status", "layout_upload_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_layout_upload_jobs_status", table_name="layout_upload_jobs")
    op.drop_index("idx_layout_upload_jobs_layout_id", table_name="layout_upload_jobs")
    op.drop_table("layout_upload_jobs")

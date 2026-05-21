"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'admin'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_admin_users_email", "admin_users", ["email"], unique=False)

    op.create_table(
        "layouts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("dxf_file_url", sa.Text(), nullable=True),
        sa.Column("excel_file_url", sa.Text(), nullable=True),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("hotspots_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("plot_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_layouts_status", "layouts", ["status"], unique=False)

    op.create_table(
        "plots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("layout_id", sa.String(length=36), nullable=False),
        sa.Column("plot_no", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'available'")),
        sa.Column("hotspot", sa.JSON(), nullable=False),
        sa.Column("dim_ft", sa.Text(), nullable=True),
        sa.Column("dim_type", sa.Text(), nullable=True),
        sa.Column("area_sq_ft", sa.Numeric(), nullable=True),
        sa.Column("area_sq_yd", sa.Numeric(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("facing", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
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
        sa.UniqueConstraint("layout_id", "plot_no"),
    )
    op.create_index("idx_plots_layout_id", "plots", ["layout_id"], unique=False)
    op.create_index("idx_plots_status", "plots", ["status"], unique=False)
    op.create_index("idx_plots_layout_status", "plots", ["layout_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plots_layout_status", table_name="plots")
    op.drop_index("idx_plots_status", table_name="plots")
    op.drop_index("idx_plots_layout_id", table_name="plots")
    op.drop_table("plots")

    op.drop_index("idx_layouts_status", table_name="layouts")
    op.drop_table("layouts")

    op.drop_index("idx_admin_users_email", table_name="admin_users")
    op.drop_table("admin_users")

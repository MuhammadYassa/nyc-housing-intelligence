"""Add measured MapPLUTO validation and unchanged counts.

Revision ID: 4e2c9f713a60
Revises: eb3717d79960
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "4e2c9f713a60"
down_revision = "eb3717d79960"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("valid_count", "unchanged_count"):
        op.add_column("import_runs", sa.Column(name, sa.BigInteger()), schema="etl")
        op.create_check_constraint(
            f"ck_import_runs_{name}_nonnegative",
            "import_runs",
            f"{name} IS NULL OR {name} >= 0",
            schema="etl",
        )
    op.add_column("import_runs", sa.Column("validation_summary", JSONB()), schema="etl")


def downgrade() -> None:
    op.drop_column("import_runs", "validation_summary", schema="etl")
    for name in ("unchanged_count", "valid_count"):
        op.drop_constraint(
            f"ck_import_runs_{name}_nonnegative", "import_runs", schema="etl"
        )
        op.drop_column("import_runs", name, schema="etl")

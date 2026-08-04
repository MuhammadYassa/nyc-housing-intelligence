"""Create database foundation.

Revision ID: b3a3a5836b80
Revises:
Create Date: 2026-07-30 18:28:20.037355
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Revision identifiers used by Alembic.
revision: str = "b3a3a5836b80"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The Docker image may already have enabled PostGIS, so this is intentionally
    # conditional.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # These schemas are owned by this migration. An unexpected pre-existing
    # schema should cause the migration to fail instead of hiding database drift.
    op.execute("CREATE SCHEMA etl")
    op.execute("CREATE SCHEMA staging")
    op.execute("CREATE SCHEMA bronze")
    op.execute("CREATE SCHEMA silver")
    op.execute("CREATE SCHEMA gold")

    op.create_table(
        "import_runs",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column(
            "dataset_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "source_dataset_id",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "pipeline_version",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "source_version",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'STARTED'"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "raw_file_path",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "checksum_sha256",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "source_row_count",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "staged_row_count",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "inserted_count",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "updated_count",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "rejected_count",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),

        # Table-level constraints
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_import_runs",
        ),
        sa.CheckConstraint(
            "char_length(btrim(dataset_name)) > 0",
            name="ck_import_runs_dataset_name_not_blank",
        ),
        sa.CheckConstraint(
            """
            status IN (
                'STARTED',
                'EXTRACTED',
                'STAGED',
                'TRANSFORMED',
                'COMPLETED',
                'FAILED'
            )
            """,
            name="ck_import_runs_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_import_runs_completed_after_started",
        ),
        sa.CheckConstraint(
            "source_row_count IS NULL OR source_row_count >= 0",
            name="ck_import_runs_source_row_count_nonnegative",
        ),
        sa.CheckConstraint(
            "staged_row_count IS NULL OR staged_row_count >= 0",
            name="ck_import_runs_staged_row_count_nonnegative",
        ),
        sa.CheckConstraint(
            "inserted_count IS NULL OR inserted_count >= 0",
            name="ck_import_runs_inserted_count_nonnegative",
        ),
        sa.CheckConstraint(
            "updated_count IS NULL OR updated_count >= 0",
            name="ck_import_runs_updated_count_nonnegative",
        ),
        sa.CheckConstraint(
            "rejected_count IS NULL OR rejected_count >= 0",
            name="ck_import_runs_rejected_count_nonnegative",
        ),
        schema="etl",
    )

    # Supports queries such as:
    # "Show me the latest MapPLUTO import runs."
    op.create_index(
        "ix_import_runs_dataset_name_started_at",
        "import_runs",
        ["dataset_name", "started_at"],
        schema="etl",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_runs_dataset_name_started_at",
        table_name="import_runs",
        schema="etl",
    )

    op.drop_table(
        "import_runs",
        schema="etl",
    )

    op.execute("DROP SCHEMA gold")
    op.execute("DROP SCHEMA silver")
    op.execute("DROP SCHEMA bronze")
    op.execute("DROP SCHEMA staging")
    op.execute("DROP SCHEMA etl")

    # Do not drop PostGIS. It is database infrastructure and other objects may
    # eventually depend on it.
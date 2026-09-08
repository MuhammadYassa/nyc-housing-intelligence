"""Track source lineage and pipeline progress in etl.import_runs.

The caller owns the connection and decides when to commit or roll back.
"""

import psycopg
from pathlib import Path
from ..models.status import ImportRunStatus


def create_import_run(
    conn: psycopg.Connection,
    dataset_name: str,
    pipeline_version: str,
    source_version: str,
    raw_file_path: Path,
    checksum_sha256: str,
) -> int:
    """Start an import and return its ID for progress updates and silver rows."""
    # Keep the file path and checksum alongside the source and pipeline versions
    # so loaded records can be traced back to the input used by this run.
    row = conn.execute(
        """
        INSERT INTO etl.import_runs (
        dataset_name,
        source_dataset_id,
        pipeline_version,
        source_version,
        status,
        raw_file_path,
        checksum_sha256
        )
        VALUES (
            %s,
            NULL,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        RETURNING id;
        """,
        (
            dataset_name,
            pipeline_version,
            source_version,
            ImportRunStatus.STARTED.value,
            str(raw_file_path),
            checksum_sha256,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError("Failed to create import run")
    return row[0]


def update_import_status(
    conn: psycopg.Connection,
    run_id: int,
    status: ImportRunStatus,
) -> None:
    """Record an intermediate stage reached by an existing import."""
    # Completion and failure use separate helpers to also record the outcome
    # and finish time. This check does not enforce the order of stages.
    if status not in {
        ImportRunStatus.EXTRACTED,
        ImportRunStatus.STAGED,
        ImportRunStatus.TRANSFORMED,
    }:
        raise ValueError("Incorrect Status Value")
    result = conn.execute(
        """
        UPDATE etl.import_runs
        SET status = %s
        WHERE id = %s
        """,
        (status.value, run_id),
    )

    # A missing run should surface as an error rather than lose progress silently.
    if result.rowcount != 1:
        raise RuntimeError(f"Import run {run_id} was not found.")


def complete_import_run(
    conn: psycopg.Connection,
    run_id: int,
    inserted_count: int,
    updated_count: int,
    rejected_count: int,
) -> None:
    """Finish a successful import with row counts supplied by the pipeline."""
    result = conn.execute(
        """
        UPDATE etl.import_runs
        SET status = %s,
        completed_at = CURRENT_TIMESTAMP,
        inserted_count = %s,
        updated_count = %s,
        rejected_count = %s,
        error_message = NULL
        WHERE id = %s
        """,
        (
            ImportRunStatus.COMPLETED.value,
            inserted_count,
            updated_count,
            rejected_count,
            run_id,
        ),
    )
    if result.rowcount != 1:
        raise RuntimeError(f"Import run {run_id} was not found.")


def fail_import_run(
    conn: psycopg.Connection,
    run_id: int,
    error_message: str,
) -> None:
    """Finish a failed import and preserve the error for later inspection.

    If a database error aborted the transaction, the caller must roll it back
    before using this connection to record the failure.
    """
    result = conn.execute(
        """
        UPDATE etl.import_runs
        SET status = %s,
        completed_at = CURRENT_TIMESTAMP,
        error_message = %s
        WHERE id = %s
        """,
        (ImportRunStatus.FAILED.value, error_message, run_id),
    )
    if result.rowcount != 1:
        raise RuntimeError(f"Import run {run_id} was not found.")

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

    if result.rowcount != 1:
        raise RuntimeError(f"Import run {run_id} was not found.")


def complete_import_run(
    conn: psycopg.Connection,
    run_id: int,
    inserted_count: int,
    updated_count: int,
    rejected_count: int,
) -> None:
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

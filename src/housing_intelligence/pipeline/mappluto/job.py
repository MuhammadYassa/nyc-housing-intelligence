"""One MapPLUTO run owns staging and commits canonical changes with its outcome."""

import argparse
import json
import logging
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

import psycopg

from ...config import Settings
from ...database import connect
from ...models.status import ImportRunStatus
from ..import_runs import (
    complete_import_run,
    create_import_run,
    fail_import_run,
    record_import_progress,
    update_import_status,
)
from .bronze import calculate_sha256, extract_mappluto, verify_bronze_artifact
from .gdal import inspect_mappluto, load_to_staging
from .source import SourceContract, contract_for_release, validate_inspection
from .transform import merge_tax_lots
from .validation import ValidationError, validate_staging

LOGGER = logging.getLogger(__name__)
PIPELINE_VERSION = "mappluto-v1"
# Fixed two-int namespace/key, independent of Python's randomized hash().
MAPPLUTO_LOCK = (741203, 1)


@contextmanager
def mappluto_lock(conn):
    if not conn.execute(
        "SELECT pg_try_advisory_lock(%s, %s)", MAPPLUTO_LOCK
    ).fetchone()[0]:
        raise RuntimeError(
            "Another MapPLUTO job owns staging; retry after it finishes."
        )
    try:
        yield
    finally:
        # Closing a broken connection also releases this session-level lock.
        if not conn.closed:
            try:
                conn.execute("SELECT pg_advisory_unlock(%s, %s)", MAPPLUTO_LOCK)
            except psycopg.Error:
                conn.close()
                LOGGER.warning(
                    "Lock connection lost; PostgreSQL releases ownership when the session ends"
                )


@dataclass(frozen=True)
class RunResult:
    run_id: int
    inserted: int
    updated: int
    unchanged: int


class MapplutoRunError(RuntimeError):
    def __init__(self, run_id: int, message: str):
        self.run_id = run_id
        super().__init__(f"MapPLUTO run {run_id} failed: {message}")


def run_mappluto(
    archive: Path,
    contract: SourceContract,
    expected_sha256: str,
    *,
    settings: Settings | None = None,
    work_root: Path = Path("data/working/mappluto"),
) -> RunResult:
    settings = settings or Settings()
    archive = archive.resolve()
    with connect(settings) as conn, mappluto_lock(conn):
        # A prior process may have been killed without reaching its handler.
        # With the lock acquired, its nonterminal run cannot be active. Atomic
        # merge/completion means none of those runs committed canonical changes.
        conn.execute(
            """UPDATE etl.import_runs SET status='FAILED', completed_at=clock_timestamp(),
               error_message='Interrupted run recovered by the next MapPLUTO owner',
               inserted_count=0, updated_count=0, unchanged_count=0
               WHERE dataset_name='MapPLUTO' AND pipeline_version=%s
                 AND status NOT IN ('COMPLETED','FAILED')""",
            (PIPELINE_VERSION,),
        )
        # Each statement outside transaction() is durable before external work.
        run_id = create_import_run(
            conn, "MapPLUTO", PIPELINE_VERSION, contract.release, archive, None
        )
        phase = "artifact"
        validation = None
        try:
            LOGGER.info("MapPLUTO run %s started", run_id)
            checksum = calculate_sha256(archive)
            record_import_progress(conn, run_id, checksum_sha256=checksum)
            verify_bronze_artifact(archive, expected_sha256)
            work_root = work_root.resolve()
            work_root.mkdir(parents=True, exist_ok=True)
            workspace = Path(tempfile.mkdtemp(prefix=f"run-{run_id}-", dir=work_root))
            LOGGER.info("Run workspace: %s", workspace)
            gdb = extract_mappluto(archive, workspace / "extracted")
            # Detect replacement/modification between verification and extraction.
            verify_bronze_artifact(archive, expected_sha256)
            update_import_status(conn, run_id, ImportRunStatus.EXTRACTED)

            phase = "inspection"
            inspection = inspect_mappluto(gdb, contract, settings)
            inspected_layers = [
                layer
                for layer in inspection.get("layers", [])
                if layer.get("name") == contract.layer
            ]
            if len(inspected_layers) == 1:
                measured = inspected_layers[0].get("featureCount")
                if type(measured) is int and measured >= 0:
                    record_import_progress(conn, run_id, source_row_count=measured)
            source_count = validate_inspection(inspection, contract)

            phase = "staging"
            load_to_staging(gdb, contract, settings)
            staged_count = conn.execute(
                "SELECT count(*) FROM staging.mappluto_source"
            ).fetchone()[0]
            record_import_progress(conn, run_id, staged_row_count=staged_count)
            update_import_status(conn, run_id, ImportRunStatus.STAGED)

            phase = "validation"
            # Hold staging stable through validation and merge. The session lock
            # spans GDAL's separate connection; this table lock also blocks SQL
            # writers that do not cooperate with the job's advisory lock.
            with conn.transaction():
                conn.execute("LOCK TABLE staging.mappluto_source IN SHARE MODE")
                validation = validate_staging(conn, contract, source_count)
                if validation.rejected or validation.summary.get("completeness"):
                    raise ValidationError(validation)
                record_import_progress(
                    conn,
                    run_id,
                    valid_count=validation.valid,
                    rejected_count=validation.rejected,
                    validation_summary=validation.summary,
                )
                phase = "merge"
                counts = merge_tax_lots(conn, contract, run_id)
                if sum(asdict(counts).values()) != validation.valid:
                    raise RuntimeError(
                        "Merge counts do not reconcile with validated rows"
                    )
                complete_import_run(
                    conn, run_id, counts.inserted, counts.updated, 0, counts.unchanged
                )
            # Completion and canonical changes become visible together at commit.
            LOGGER.info("MapPLUTO run %s completed: %s", run_id, counts)
            return RunResult(run_id, counts.inserted, counts.updated, counts.unchanged)
        except (Exception, KeyboardInterrupt) as error:
            # transaction() rolled back first. Store diagnostics independently.
            message = f"{phase}: {type(error).__name__}: {error}"
            try:
                with connect(settings) as failure_conn:
                    outcome = failure_conn.execute(
                        "SELECT status, inserted_count, updated_count, unchanged_count FROM etl.import_runs WHERE id=%s",
                        (run_id,),
                    ).fetchone()
                    if outcome and outcome[0] == "COMPLETED":
                        # A COMMIT acknowledgement can be lost while the commit
                        # itself succeeds. Trust the atomically committed outcome.
                        return RunResult(run_id, *outcome[1:])
                    if isinstance(error, ValidationError):
                        validation = error.result
                    with failure_conn.transaction():
                        if validation is not None:
                            record_import_progress(
                                failure_conn,
                                run_id,
                                staged_row_count=validation.received,
                                valid_count=validation.valid,
                                rejected_count=validation.rejected,
                                validation_summary=validation.summary,
                            )
                        fail_import_run(failure_conn, run_id, message)
            except Exception:
                LOGGER.exception(
                    "Could not persist outcome for run %s; inspect/reconcile it before retry",
                    run_id,
                )
            raise MapplutoRunError(run_id, message) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument(
        "--sha256",
        required=True,
        help="Expected SHA-256 of the selected source archive",
    )
    parser.add_argument("--work-root", type=Path, default=Path("data/working/mappluto"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = run_mappluto(
            args.archive,
            contract_for_release(args.release),
            args.sha256,
            work_root=args.work_root,
        )
    except Exception as error:
        LOGGER.error("%s", error)
        return 1
    print(json.dumps(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

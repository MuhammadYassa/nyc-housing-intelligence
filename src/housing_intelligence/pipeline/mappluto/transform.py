"""Set-based current-state merge. The job owns the surrounding transaction."""

from dataclasses import dataclass
from importlib.resources import files

from .source import SourceContract


@dataclass(frozen=True)
class MergeCounts:
    inserted: int
    updated: int
    unchanged: int


def merge_tax_lots(conn, contract: SourceContract, run_id: int) -> MergeCounts:
    # Serialize other canonical writers as well as cooperating MapPLUTO jobs.
    # Readers remain available. No missing source row is deleted or retired.
    conn.execute("LOCK TABLE silver.tax_lots IN SHARE ROW EXCLUSIVE MODE")
    sql = files(__package__).joinpath("merge.sql").read_text(encoding="utf-8")
    inserted, updated = conn.execute(
        sql, {"source_year": contract.source_year, "run_id": run_id}
    ).fetchone()
    total = conn.execute("SELECT count(*) FROM staging.mappluto_source").fetchone()[0]
    return MergeCounts(inserted, updated, total - inserted - updated)

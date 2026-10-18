"""Fail the whole snapshot on invalid rows; never silently choose duplicates."""

from dataclasses import dataclass
from importlib.resources import files

from .source import REQUIRED_FIELDS, STAGING_TYPES, SourceContract


@dataclass(frozen=True)
class ValidationResult:
    received: int
    valid: int
    rejected: int
    summary: dict


class ValidationError(ValueError):
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(f"Snapshot validation failed: {result.summary}")


def validate_staging(
    conn, contract: SourceContract, source_count: int
) -> ValidationResult:
    received = conn.execute("SELECT count(*) FROM staging.mappluto_source").fetchone()[0]
    fields = dict(
        conn.execute(
            """SELECT column_name, udt_name FROM information_schema.columns
           WHERE table_schema = 'staging' AND table_name = 'mappluto_source'"""
        ).fetchall()
    )
    incompatible = [
        name
        for name, kind in REQUIRED_FIELDS.items()
        if fields.get(name) not in STAGING_TYPES[kind]
    ]
    if fields.get("shape") != "geometry":
        incompatible.append("shape")
    if incompatible:
        raise ValidationError(
            ValidationResult(received, 0, received, {"schema": incompatible})
        )
    sql = files(__package__).joinpath("validate.sql").read_text(encoding="utf-8")
    received, valid, summary = conn.execute(
        sql, {"release": contract.release, "srid": contract.srid}
    ).fetchone()
    if received != source_count or received != contract.expected_count or received == 0:
        summary["completeness"] = {
            "source": source_count,
            "staged": received,
            "expected": contract.expected_count,
        }
    return ValidationResult(received, valid, received - valid, summary)

import json
import shutil
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from conftest import lot, stage

from housing_intelligence.database import connect
from housing_intelligence.pipeline.import_runs import create_import_run
from housing_intelligence.pipeline.mappluto import job
from housing_intelligence.pipeline.mappluto.bronze import calculate_sha256
from housing_intelligence.pipeline.mappluto.gdal import _run_command, gdal_environment
from housing_intelligence.pipeline.mappluto.transform import merge_tax_lots
from housing_intelligence.pipeline.mappluto.validation import (
    ValidationError,
    validate_staging,
)

pytestmark = pytest.mark.integration


def run(archive, contract, db_settings, tmp_path):
    return job.run_mappluto(
        archive,
        contract,
        calculate_sha256(archive),
        settings=db_settings,
        work_root=tmp_path / "runs",
    )


def test_migration_bootstrap(db):
    assert (
        db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == "4e2c9f713a60"
    )
    assert db.execute("SELECT postgis_version()").fetchone()[0]
    assert (
        db.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname='silver' AND indexname='ix_tax_lots_geom'"
        ).fetchone()[0]
        == 1
    )
    assert (
        db.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_schema='etl' AND table_name='import_runs' AND column_name IN ('valid_count','unchanged_count','validation_summary')"
        ).fetchone()[0]
        == 3
    )


def test_valid_stage(db, contract):
    stage(db, [lot()])
    result = validate_staging(db, contract, 1)
    assert (result.received, result.valid, result.rejected) == (1, 1, 0)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"bbl": 1000010001.8}, "invalid_identity"),
        ({"bbl": None}, "invalid_identity"),
        ({"bbl": float("nan")}, "invalid_identity"),
        ({"block": 2}, "invalid_identity"),
        ({"borough": "BX"}, "invalid_identity"),
        ({"shape": None}, "invalid_geometry"),
        ({"shape": "POLYGON EMPTY"}, "invalid_geometry"),
        ({"shape": "POLYGON((0 0,10 10,10 0,0 10,0 0))"}, "invalid_geometry"),
        ({"shape": "POINT(0 0)"}, "invalid_geometry"),
        ({"srid": 4326}, "invalid_geometry"),
        ({"version": "25v1"}, "wrong_release"),
        ({"numfloors": float("inf")}, "invalid_attributes"),
        ({"unitsres": -1}, "invalid_attributes"),
        ({"latitude": float("nan")}, "invalid_attributes"),
    ],
)
def test_invalid_stage(db, contract, changes, reason):
    stage(db, [lot(**changes)])
    result = validate_staging(db, contract, 1)
    assert result.rejected == 1 and result.valid == 0
    assert result.summary[reason] == 1


def test_duplicates_reject_every_copy(db, contract):
    stage(db, [lot(), lot(ownername="DIFFERENT")])
    result = validate_staging(db, replace(contract, expected_count=2), 2)
    assert result.rejected == 2
    assert result.summary["duplicate_identity_rows"] == 2


def test_missing_stage_field(db, contract):
    stage(db, [lot()])
    db.execute("ALTER TABLE staging.mappluto_source DROP COLUMN address")
    with pytest.raises(ValidationError) as error:
        validate_staging(db, contract, 1)
    assert error.value.result.summary == {"schema": ["address"]}


def test_partial_stage(db, contract):
    stage(db, [lot()])
    result = validate_staging(db, replace(contract, expected_count=2), 2)
    assert result.summary["completeness"]["staged"] == 1


def test_merge_counts_and_lineage(db, contract):
    def merge(rows):
        stage(db, rows)
        selected = replace(contract, expected_count=len(rows))
        assert validate_staging(db, selected, len(rows)).rejected == 0
        run_id = create_import_run(
            db, "MapPLUTO", "test", "26v1", Path("source.zip"), "A" * 64
        )
        with db.transaction():
            counts = merge_tax_lots(db, selected, run_id)
        return counts, run_id

    initial, first_run = merge([lot(), lot(bbl=1000010002.0, lot=2)])
    assert (initial.inserted, initial.updated, initial.unchanged) == (2, 0, 0)
    original = db.execute("SELECT * FROM silver.tax_lots ORDER BY bbl").fetchall()
    repeat, _ = merge([lot(), lot(bbl=1000010002.0, lot=2)])
    assert (repeat.inserted, repeat.updated, repeat.unchanged) == (0, 0, 2)
    assert (
        original == db.execute("SELECT * FROM silver.tax_lots ORDER BY bbl").fetchall()
    )
    changed, latest_run = merge(
        [
            lot(ownername="NEW OWNER"),
            lot(bbl=1000010002.0, lot=2),
            lot(bbl=1000010003.0, lot=3, yearbuilt=0, zipcode=0, cd=0),
        ]
    )
    assert (changed.inserted, changed.updated, changed.unchanged) == (1, 1, 1)
    assert db.execute(
        "SELECT source_import_run_id FROM silver.tax_lots ORDER BY bbl"
    ).fetchall() == [(latest_run,), (first_run,), (latest_run,)]
    assert db.execute(
        "SELECT address,latitude,longitude,year_built FROM silver.tax_lots WHERE bbl='1000010001'"
    ).fetchone() == ("1 TEST STREET", 40.5, -73.9, 1900)
    assert db.execute(
        "SELECT year_built,zip_code,community_district FROM silver.tax_lots WHERE bbl='1000010003'"
    ).fetchone() == (None, None, None)
    merge([lot(ownername="NEW OWNER")])
    assert db.execute("SELECT count(*) FROM silver.tax_lots").fetchone()[0] == 3


def test_success_is_visible_only_after_commit(
    db, db_settings, job_source, archive, contract, tmp_path, monkeypatch
):
    contract = job_source([lot()], contract)
    complete = job.complete_import_run

    def observe(conn, run_id, *counts):
        complete(conn, run_id, *counts)
        with connect(db_settings) as observer:
            assert (
                observer.execute(
                    "SELECT status FROM etl.import_runs WHERE id=%s", (run_id,)
                ).fetchone()[0]
                == "STAGED"
            )
            assert (
                observer.execute("SELECT count(*) FROM silver.tax_lots").fetchone()[0]
                == 0
            )

    monkeypatch.setattr(job, "complete_import_run", observe)
    result = run(archive, contract, db_settings, tmp_path)
    row = db.execute(
        "SELECT status,source_row_count,staged_row_count,valid_count,rejected_count,inserted_count,updated_count,unchanged_count,completed_at>started_at FROM etl.import_runs WHERE id=%s",
        (result.run_id,),
    ).fetchone()
    assert row == ("COMPLETED", 1, 1, 1, 0, 1, 0, 0, True)


@pytest.mark.parametrize("failure", ["gdal", "validation", "after_merge"])
def test_failed_job_is_durable_and_canonical_is_atomic(
    db, db_settings, job_source, archive, contract, tmp_path, monkeypatch, failure
):
    contract = job_source(
        [lot(bbl=1000010001.8)] if failure == "validation" else [lot()], contract
    )
    if failure == "gdal":

        def fail(*args):
            raise RuntimeError("GDAL failed")

        monkeypatch.setattr(job, "load_to_staging", fail)
    if failure == "after_merge":
        complete = job.complete_import_run

        def fail(conn, run_id, *counts):
            complete(conn, run_id, *counts)
            # Canonical data and COMPLETED have been written, but not committed.
            raise RuntimeError("injected failure before commit")

        monkeypatch.setattr(job, "complete_import_run", fail)
    with pytest.raises(job.MapplutoRunError) as error:
        run(archive, contract, db_settings, tmp_path)
    assert db.execute("SELECT count(*) FROM silver.tax_lots").fetchone()[0] == 0
    status, message, inserted = db.execute(
        "SELECT status,error_message,inserted_count FROM etl.import_runs WHERE id=%s",
        (error.value.run_id,),
    ).fetchone()
    assert status == "FAILED" and message and inserted == 0
    if failure == "validation":
        assert db.execute(
            "SELECT valid_count,rejected_count FROM etl.import_runs"
        ).fetchone() == (0, 1)
    elif failure == "after_merge":
        assert db.execute(
            "SELECT valid_count,rejected_count FROM etl.import_runs"
        ).fetchone() == (1, 0)
    # A subsequent job can acquire ownership after every kind of failure.
    with connect(db_settings) as other, job.mappluto_lock(other):
        pass


def test_sql_merge_error_preserves_previous_canonical_state(
    db, db_settings, job_source, archive, contract, tmp_path
):
    contract = job_source([lot()], contract)
    run(archive, contract, db_settings, tmp_path)
    before = db.execute("SELECT * FROM silver.tax_lots").fetchall()
    db.execute(
        "ALTER TABLE silver.tax_lots ADD CONSTRAINT test_owner CHECK (owner_name <> 'REJECT')"
    )
    try:
        contract = job_source(
            [lot(ownername="REJECT"), lot(bbl=1000010002.0, lot=2)], contract
        )
        with pytest.raises(job.MapplutoRunError):
            run(archive, contract, db_settings, tmp_path)
        assert db.execute("SELECT * FROM silver.tax_lots").fetchall() == before
        assert (
            db.execute(
                "SELECT status FROM etl.import_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            == "FAILED"
        )
    finally:
        db.execute("ALTER TABLE silver.tax_lots DROP CONSTRAINT test_owner")


def test_competing_job_cannot_overwrite_staging(
    db, db_settings, job_source, archive, contract, tmp_path
):
    stage(db, [lot(ownername="ORIGINAL")])
    contract = job_source([lot(ownername="OVERWRITTEN")], contract)
    with job.mappluto_lock(db), pytest.raises(RuntimeError, match="Another MapPLUTO"):
        run(archive, contract, db_settings, tmp_path)
    assert (
        db.execute("SELECT ownername FROM staging.mappluto_source").fetchone()[0]
        == "ORIGINAL"
    )
    assert db.execute("SELECT count(*) FROM etl.import_runs").fetchone()[0] == 0


def test_interrupted_run_recovered_without_rewriting_old_runs(
    db, db_settings, job_source, archive, contract, tmp_path
):
    interrupted = create_import_run(
        db, "MapPLUTO", job.PIPELINE_VERSION, "26v1", archive, None
    )
    legacy = create_import_run(db, "MapPLUTO", "legacy-manual", "26v1", archive, None)
    contract = job_source([lot()], contract)
    run(archive, contract, db_settings, tmp_path)
    assert (
        db.execute(
            "SELECT status FROM etl.import_runs WHERE id=%s", (interrupted,)
        ).fetchone()[0]
        == "FAILED"
    )
    assert (
        db.execute(
            "SELECT status FROM etl.import_runs WHERE id=%s", (legacy,)
        ).fetchone()[0]
        == "STARTED"
    )


def test_checksum_failure_is_recorded(db, db_settings, archive, contract, tmp_path):
    with pytest.raises(job.MapplutoRunError, match="SHA256 Hash do not match!"):
        job.run_mappluto(
            archive,
            contract,
            "0" * 64,
            settings=db_settings,
            work_root=tmp_path / "runs",
        )
    status, checksum = db.execute(
        "SELECT status,checksum_sha256 FROM etl.import_runs"
    ).fetchone()
    assert status == "FAILED" and checksum == calculate_sha256(archive)
    assert not (tmp_path / "runs").exists()


def test_partial_load_cannot_promote(
    db, db_settings, job_source, archive, contract, tmp_path, monkeypatch
):
    from conftest import inspection_for

    selected = job_source([lot()], contract)
    selected = replace(selected, expected_count=2)
    monkeypatch.setattr(job, "inspect_mappluto", lambda *args: inspection_for(selected))
    with pytest.raises(job.MapplutoRunError):
        run(archive, selected, db_settings, tmp_path)
    assert db.execute("SELECT count(*) FROM silver.tax_lots").fetchone()[0] == 0
    assert db.execute(
        "SELECT status,source_row_count,staged_row_count FROM etl.import_runs"
    ).fetchone() == ("FAILED", 2, 1)


def test_terminal_outcome_cannot_be_reopened(
    db, db_settings, job_source, archive, contract, tmp_path
):
    from housing_intelligence.models.status import ImportRunStatus
    from housing_intelligence.pipeline.import_runs import (
        fail_import_run,
        update_import_status,
    )

    selected = job_source([lot()], contract)
    result = run(archive, selected, db_settings, tmp_path)
    with pytest.raises(RuntimeError):
        update_import_status(db, result.run_id, ImportRunStatus.STAGED)
    with pytest.raises(RuntimeError):
        fail_import_run(db, result.run_id, "late failure")
    assert db.execute("SELECT status FROM etl.import_runs").fetchone()[0] == "COMPLETED"


def test_real_gdal_archive_to_canonical(db, db_settings, archive, contract, tmp_path):
    if not shutil.which(db_settings.ogr2ogr_executable) or not shutil.which(
        db_settings.ogrinfo_executable
    ):
        pytest.skip(
            "GDAL executables unavailable; other integration tests still exercise real PostGIS"
        )
    row = lot()
    properties = {k: v for k, v in row.items() if k not in {"shape", "srid"}}
    geojson = tmp_path / "fixture.geojson"
    geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": properties,
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [1000000, 200000],
                                    [1000010, 200000],
                                    [1000010, 200010],
                                    [1000000, 200010],
                                    [1000000, 200000],
                                ]
                            ],
                        },
                    }
                ],
            }
        )
    )
    gdb = tmp_path / "fixture.gdb"
    _run_command(
        [
            db_settings.ogr2ogr_executable,
            "-f",
            "OpenFileGDB",
            str(gdb),
            str(geojson),
            "-nln",
            contract.layer,
            "-a_srs",
            "EPSG:2263",
            "-nlt",
            "MULTIPOLYGON",
        ],
        timeout=60,
        env=gdal_environment(db_settings),
    )
    with ZipFile(archive, "w") as output:
        for path in sorted(gdb.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(tmp_path))
    initial = run(archive, contract, db_settings, tmp_path)
    repeat = run(archive, contract, db_settings, tmp_path)
    assert initial.inserted == 1 and repeat.unchanged == 1
    assert db.execute(
        "SELECT ST_SRID(geom),year_built,latitude,longitude FROM silver.tax_lots"
    ).fetchone() == (2263, 1900, 40.5, -73.9)

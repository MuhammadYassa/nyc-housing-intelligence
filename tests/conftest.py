"""Integration tests create and drop only their own randomly named database."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine

from alembic import command
from housing_intelligence.config import Settings
from housing_intelligence.database import connect, sqlalchemy_url
from housing_intelligence.pipeline.mappluto.source import (
    REQUIRED_FIELDS,
    SourceContract,
)

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        help="Run tests in a disposable PostGIS database",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Pass --integration to test real PostgreSQL/PostGIS"
                    )
                )


@pytest.fixture(scope="session")
def db_settings():
    original = Settings()
    name = "mappluto_test_" + uuid4().hex
    isolated = original.model_copy(update={"database_name": name})
    with connect(original) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        engine = create_engine(sqlalchemy_url(isolated))
        try:
            with engine.begin() as conn:
                config = Config(str(ROOT / "alembic.ini"))
                config.attributes["connection"] = conn
                command.upgrade(config, "head")
        finally:
            engine.dispose()
        yield isolated
    finally:
        assert name.startswith("mappluto_test_") and name != original.database_name
        with connect(original) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def db(db_settings):
    with connect(db_settings) as conn:
        conn.execute("DROP TABLE IF EXISTS staging.mappluto_source")
        conn.execute("TRUNCATE silver.tax_lots, etl.import_runs RESTART IDENTITY")
        yield conn


@pytest.fixture
def contract():
    return SourceContract("26v1", "MapPLUTO_26v1_clipped", 2026, 1)


def inspection_for(contract):
    return {
        "driverShortName": "OpenFileGDB",
        "layers": [
            {
                "name": contract.layer,
                "featureCount": contract.expected_count,
                "fields": [{"name": k, "type": v} for k, v in REQUIRED_FIELDS.items()],
                "geometryFields": [
                    {
                        "type": "MultiPolygon",
                        "coordinateSystem": {
                            "projjson": {"id": {"authority": "EPSG", "code": 2263}},
                        },
                    }
                ],
            }
        ],
    }


def lot(**changes):
    result = dict(
        bbl=1000010001.0,
        borocode=1,
        borough="MN",
        block=1,
        lot=1,
        address=" 1 TEST STREET ",
        zipcode=10001,
        cd=101,
        bldgclass="A1",
        landuse="01",
        ownername=" TEST OWNER ",
        lotarea=1000,
        bldgarea=2000,
        numbldgs=1,
        numfloors=3.5,
        unitsres=2,
        unitstotal=2,
        yearbuilt=1900,
        latitude=40.5,
        longitude=-73.9,
        version="26v1",
        shape="POLYGON((1000000 200000,1000010 200000,1000010 200010,1000000 200010,1000000 200000))",
        srid=2263,
    )
    result.update(changes)
    return result


def stage(conn, rows):
    types = {"Integer": "integer", "Real": "double precision", "String": "text"}
    columns = ", ".join(f'"{k}" {types[v]}' for k, v in REQUIRED_FIELDS.items())
    conn.execute("DROP TABLE IF EXISTS staging.mappluto_source")
    conn.execute(f"CREATE TABLE staging.mappluto_source ({columns}, shape geometry)")
    names = list(REQUIRED_FIELDS)
    query = sql.SQL(
        "INSERT INTO staging.mappluto_source ({}, shape) VALUES ({}, ST_GeomFromText(%s, %s))"
    ).format(
        sql.SQL(", ").join(map(sql.Identifier, names)),
        sql.SQL(", ").join(sql.Placeholder() for _ in names),
    )
    for row in rows:
        conn.execute(query, [*[row[k] for k in names], row["shape"], row["srid"]])


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "source.zip"
    with ZipFile(path, "w") as output:
        output.writestr("source.gdb/table", "synthetic source")
    return path


@pytest.fixture
def job_source(monkeypatch, db_settings):
    """Mock only external GDAL input; all job database behavior remains real."""
    from housing_intelligence.pipeline.mappluto import job

    def configure(rows, contract):
        adjusted = replace(contract, expected_count=len(rows))
        monkeypatch.setattr(
            job, "inspect_mappluto", lambda *args: inspection_for(adjusted)
        )

        def load(*args):
            with connect(db_settings) as conn:
                stage(conn, rows)

        monkeypatch.setattr(job, "load_to_staging", load)
        return adjusted

    return configure

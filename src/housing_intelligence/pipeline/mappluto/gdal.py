"""Inspect the MapPLUTO geodatabase and load its source layer into staging."""

import json
import os
import subprocess
from pathlib import Path

from ...config import Settings
from ...database import gdal_connection
from .source import SourceContract


def gdal_environment(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    if settings.gdal_proj_data:
        # QGIS and a separate PostgreSQL install can ship incompatible PROJ DBs.
        env["PROJ_DATA"] = settings.gdal_proj_data
        env["PROJ_LIB"] = settings.gdal_proj_data
    return env


def _run_command(
    arguments: list[str],
    env: dict[str, str] | None = None,
    *,
    timeout: int,
) -> str:
    """Return command output, raising an error with GDAL's diagnostics on failure."""
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            check=True,
            env=env,
            timeout=timeout,
        )
        return result.stdout
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"GDAL command exceeded {timeout} seconds") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Command {e.cmd} failed with exit code {e.returncode}.\n"
            f"GDAL error: {e.stderr}"
        ) from e


def inspect_mappluto(
    gdb_path: Path, contract: SourceContract, settings: Settings
) -> dict:
    """Read layer information as JSON without modifying the source geodatabase."""
    ogrinfo_output = _run_command(
        [settings.ogrinfo_executable, "-json", "-ro", str(gdb_path), contract.layer],
        env=gdal_environment(settings),
        timeout=settings.gdal_inspect_timeout_seconds,
    )
    ogrinfo = json.loads(ogrinfo_output)
    return ogrinfo


def load_to_staging(
    gdb_path: Path,
    contract: SourceContract,
    settings: Settings,
) -> None:
    """Replace staging.mappluto_source with the selected geodatabase layer."""
    gdal_pg_connection_string = gdal_connection(settings)

    # Inherit the local GDAL environment and add the password for this subprocess.
    env = gdal_environment(settings)

    # Keep the password out of command arguments, which can appear in errors.
    env["PGPASSWORD"] = settings.database_password.get_secret_value()

    _run_command(
        [
            settings.ogr2ogr_executable,
            "-f",
            "PostgreSQL",
            gdal_pg_connection_string,
            str(gdb_path),
            contract.layer,
            "-nln",
            "staging.mappluto_source",
            # Each load replaces staging so reruns do not append duplicate rows.
            "-overwrite",
            # Normalize polygons to multipart geometry while keeping the source CRS.
            "-nlt",
            "PROMOTE_TO_MULTI",
            # Retain source feature IDs as objectid for tracing staged records.
            "-preserve_fid",
            "-lco",
            "FID=objectid",
            # The silver transform expects shape and lowercase source field names.
            "-lco",
            "GEOMETRY_NAME=shape",
            "-lco",
            "LAUNDER=YES",
            # Spatial indexing is defined on silver.tax_lots by its migration.
            "-lco",
            "SPATIAL_INDEX=NONE",
            "-progress",
        ],
        env=env,
        timeout=settings.gdal_load_timeout_seconds,
    )

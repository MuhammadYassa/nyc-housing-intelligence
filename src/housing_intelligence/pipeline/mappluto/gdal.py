"""Inspect the MapPLUTO geodatabase and load its source layer into staging."""

from pathlib import Path
import subprocess
import json
import os
from ...config import settings

OGRINFO_EXECUTABLE = settings.ogrinfo_executable
OGR2OGR_EXECUTABLE = settings.ogr2ogr_executable
# This layer name belongs to the 26v1 release used by the pipeline.
MAPPLUTO_LAYER = "MapPLUTO_26v1_clipped"


def _run_command(
    arguments: list[str],
    env: dict[str, str] | None = None,
) -> str:
    """Return command output, raising an error with GDAL's diagnostics on failure."""
    try:
        result = subprocess.run(
            arguments, capture_output=True, text=True, check=True, env=env
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Command {e.cmd} failed with exit code {e.returncode}.\n"
            f"GDAL error: {e.stderr}"
        ) from e


def inspect_mappluto(gdb_path: Path) -> dict:
    """Read layer information as JSON without modifying the source geodatabase."""
    ogrinfo_output = _run_command(
        [OGRINFO_EXECUTABLE, "-json", "-ro", str(gdb_path), MAPPLUTO_LAYER]
    )
    ogrinfo = json.loads(ogrinfo_output)
    return ogrinfo


def load_to_staging(
    gdb_path: Path,
    layer_name: str,
) -> None:
    """Replace staging.mappluto_source with the selected geodatabase layer."""
    gdal_pg_connection_string = (
        f"PG:host={settings.database_host} "
        f"port={settings.database_port} "
        f"dbname={settings.database_name} "
        f"user={settings.database_user}"
    )

    # Inherit the local GDAL environment and add the password for this subprocess.
    env = os.environ.copy()

    # Keep the password out of command arguments, which can appear in errors.
    env["PGPASSWORD"] = settings.database_password.get_secret_value()

    _run_command(
        [
            OGR2OGR_EXECUTABLE,
            "-f",
            "PostgreSQL",
            gdal_pg_connection_string,
            str(gdb_path),
            layer_name,
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
    )

from pathlib import Path
import subprocess
import json
import os
from ...config import settings

OGRINFO_EXECUTABLE = settings.ogrinfo_executable
OGR2OGR_EXECUTABLE = settings.ogr2ogr_executable
MAPPLUTO_LAYER = "MapPLUTO_26v1_clipped"


def _run_command(
    arguments: list[str],
    env: dict[str, str] | None = None,
) -> str:
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
    ogrinfo_output = _run_command(
        [OGRINFO_EXECUTABLE, "-json", "-ro", str(gdb_path), MAPPLUTO_LAYER]
    )
    ogrinfo = json.loads(ogrinfo_output)
    return ogrinfo


def load_to_staging(
    gdb_path: Path,
    layer_name: str,
) -> None:
    gdal_pg_connection_string = (
        f"PG:host={settings.database_host} "
        f"port={settings.database_port} "
        f"dbname={settings.database_name} "
        f"user={settings.database_user}"
    )

    env = os.environ.copy()

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
            "-overwrite",
            "-nlt",
            "PROMOTE_TO_MULTI",
            "-preserve_fid",
            "-lco",
            "FID=objectid",
            "-lco",
            "GEOMETRY_NAME=shape",
            "-lco",
            "LAUNDER=YES",
            "-lco",
            "SPATIAL_INDEX=NONE",
            "-progress",
        ],
        env=env,
    )


if __name__ == "__main__":
    gdb_path = Path("data/working/mappluto/26v1/MapPLUTO26v1.gdb")

    load_to_staging(
        gdb_path,
        MAPPLUTO_LAYER,
    )

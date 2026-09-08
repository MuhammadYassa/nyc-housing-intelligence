from pathlib import Path
from collections.abc import Iterator
from zipfile import ZipFile
import shutil
import hashlib


def read_in_chunks(path: Path, chunk_size: int) -> Iterator[bytes]:
    """Yield file bytes in chunks so large source files stay out of memory."""
    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk


def calculate_sha256(path: Path) -> str:
    """Return the source file's SHA-256 hex digest for etl.import_runs."""
    # The checksum identifies the exact file contents behind an import,
    # even when the source filename or release label stays the same.
    sha256_hash = hashlib.sha256()
    # Read 1 MiB at a time to keep memory use independent of the file size.
    for chunk in read_in_chunks(path, 1024 * 1024):
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest().upper()


def verify_bronze_artifact(
    path: Path,
    expected_sha256: str,
) -> None:
    """Check that the stored source file exists and matches its expected checksum."""
    if not path.is_file():
        raise FileNotFoundError(f"Bronze artifact not found: {path}")

    actual_sha256 = calculate_sha256(path)

    # Hex letter casing does not change the checksum's value.
    if actual_sha256 != expected_sha256.upper():
        raise ValueError("SHA256 Hash do not match!")


def extract_mappluto(
    archive_path: Path,
    working_directory: Path,
) -> Path:
    """Extract MapPLUTO into a fresh working directory and return its .gdb path.

    The working directory must be disposable: any existing contents are deleted.
    """
    if not archive_path.is_file():
        raise FileNotFoundError("Archive File Not Found!")

    # Clear leftovers from earlier runs so releases cannot get mixed together.
    if working_directory.is_dir():
        shutil.rmtree(working_directory)
    working_directory.mkdir(parents=True, exist_ok=True)

    with ZipFile(archive_path, "r") as archive:
        archive.extractall(working_directory)

    # A file geodatabase is a directory and may be nested inside the archive.
    gdb_list = [path for path in working_directory.rglob("*.gdb") if path.is_dir()]

    # Require one source geodatabase so the next stage has an unambiguous input.
    if len(gdb_list) < 1:
        raise FileNotFoundError("GeoSpatial Database File Not Found!")
    elif len(gdb_list) > 1:
        raise ValueError("Multiple GeoSpatial Database Files Found")

    return gdb_list[0]

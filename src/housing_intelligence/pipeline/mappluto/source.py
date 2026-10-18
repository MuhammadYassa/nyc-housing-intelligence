"""Reviewed release contracts, separate from measured ingestion metadata."""

from dataclasses import dataclass

# Only fields consumed by the canonical mapping are required. GDAL lowercases
# them during staging; numeric categories also define acceptable staging types.
REQUIRED_FIELDS = {
    "bbl": "Real",
    "borocode": "Integer",
    "borough": "String",
    "block": "Integer",
    "lot": "Integer",
    "address": "String",
    "zipcode": "Integer",
    "cd": "Integer",
    "bldgclass": "String",
    "landuse": "String",
    "ownername": "String",
    "lotarea": "Integer",
    "bldgarea": "Integer",
    "numbldgs": "Integer",
    "numfloors": "Real",
    "unitsres": "Integer",
    "unitstotal": "Integer",
    "yearbuilt": "Integer",
    "latitude": "Real",
    "longitude": "Real",
    "version": "String",
}
STAGING_TYPES = {
    "Integer": {"int2", "int4", "int8"},
    "Real": {"float4", "float8", "numeric"},
    "String": {"text", "varchar", "bpchar"},
}


@dataclass(frozen=True)
class SourceContract:
    release: str
    layer: str
    source_year: int
    expected_count: int
    srid: int = 2263


CONTRACTS = {
    "26v1": SourceContract("26v1", "MapPLUTO_26v1_clipped", 2026, 856614),
}


def contract_for_release(release: str) -> SourceContract:
    try:
        return CONTRACTS[release]
    except KeyError:
        raise ValueError(
            f"Unsupported MapPLUTO release {release!r}; add a reviewed source contract first"
        ) from None


def validate_inspection(inspection: dict, contract: SourceContract) -> int:
    if inspection.get("driverShortName") != "OpenFileGDB":
        raise ValueError("Expected the OpenFileGDB source driver")
    layers = [
        layer
        for layer in inspection.get("layers", [])
        if layer.get("name") == contract.layer
    ]
    if len(layers) != 1:
        raise ValueError(f"Expected exactly one layer named {contract.layer}")
    layer = layers[0]
    fields = {field["name"].lower(): field["type"] for field in layer.get("fields", [])}
    problems = [
        name for name, kind in REQUIRED_FIELDS.items() if fields.get(name) != kind
    ]
    if problems:
        raise ValueError(
            f"Missing or incompatible source fields: {', '.join(problems)}"
        )
    geometry = layer.get("geometryFields", [])
    if len(geometry) != 1 or geometry[0].get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Expected one two-dimensional polygon geometry field")
    crs_id = geometry[0].get("coordinateSystem", {}).get("projjson", {}).get("id", {})
    if crs_id.get("authority") != "EPSG" or str(crs_id.get("code")) != str(
        contract.srid
    ):
        raise ValueError(f"Expected source CRS EPSG:{contract.srid}")
    count = layer.get("featureCount")
    if type(count) is not int or count <= 0 or count != contract.expected_count:
        raise ValueError(
            f"Incomplete source: measured {count}, expected {contract.expected_count} for {contract.release}"
        )
    return count

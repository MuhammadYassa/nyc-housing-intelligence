# MapPLUTO 26v1 ingestion contract

Executable release metadata lives in
`src/housing_intelligence/pipeline/mappluto/source.py`. Only reviewed releases
are accepted. 26v1 expects `MapPLUTO_26v1_clipped`, OpenFileGDB, 856,614 source
features, and two-dimensional Polygon/MultiPolygon geometry in EPSG:2263.
This count is a release-specific completeness expectation, not a hardcoded
measurement: each run records inspection and database counts independently.
Future releases require a reviewed descriptor rather than reusing this count.

All fields below must exist with the documented source numeric/string types.
Staging preserves source `objectid`; canonical identity is BBL, not objectid.

## Validation and normalization

- BBL is required, finite, integral, within the ten-digit NYC borough range,
  and equal to borough/block/lot components. Fractional BBLs fail the snapshot.
- Borough must match its numeric code; block is 0–99999 and lot is 0–9999.
- Every BBL must occur once. Every row participating in a duplicate is rejected;
  there is no arbitrary winner or geometry repair.
- Geometry must be present, nonempty, valid, two-dimensional, polygonal, and
  SRID 2263. Polygons are promoted to MultiPolygon without changing CRS.
- Every row's trimmed version must match the selected release. Source/staging
  counts must equal the reviewed expectation, and zero-row snapshots fail.
- Areas and counts must be nonnegative and fit target types; floors must fit
  numeric(6,2). Coordinates must fit latitude/longitude ranges. Non-null ZIP
  codes must be zero or five-digit values; community district must fit smallint.
- Optional blank text becomes NULL. Zero ZIP/community district becomes NULL.
  Year built outside 1624 through the release year becomes NULL, preserving the
  prototype's unknown/invalid-year normalization. Floors round to two decimals.

Any invalid row, incompatible schema, duplicate, or completeness failure rejects
the **whole snapshot**. `valid_count` counts individually valid staged rows even
when another row fails; `rejected_count` counts invalid rows once. Diagnostic
category counts in `validation_summary` can overlap. A completeness failure may
have zero invalid rows while still preventing promotion. Unknown counts remain
NULL when failure occurs before they can be measured.

## Merge and provenance

The maintained SQL is `pipeline/mappluto/merge.sql` inside the Python package;
the former standalone promotion script has been removed. PostgreSQL 17 MERGE
reports inserted/updated counts; remaining validated rows are unchanged.
Change detection compares normalized attributes, exact geometry bytes, and
release version. Unchanged rows retain all timestamps and row lineage. Updates
retain `ingested_at` and replace `updated_at`/`source_import_run_id`; new rows set
both timestamps and their source run. Lots missing from a snapshot are untouched.

The input archive, checksum, release, and import run provide source provenance.
No generalized lot history is implemented. Keep prior archives available before
using the merge for later source corrections/releases.

## Field mapping

| Source field | Silver field            | Purpose                                 |
| ------------ | --------------------- | --------------------------------------- |
| `BBL`        | `bbl`                 | Primary tax-lot identifier              |
| `BoroCode`   | `borough_code`        | Numeric borough identifier              |
| `Borough`    | `borough`             | Human-readable borough code             |
| `Block`      | `tax_block`           | BBL component                           |
| `Lot`        | `tax_lot`             | BBL component                           |
| `Address`    | `address`             | Display address                         |
| `ZipCode`    | `zip_code`            | Geographic/display information          |
| `CD`         | `community_district`  | Neighborhood-level analysis             |
| `BldgClass`  | `building_class`      | Property type and peer groups           |
| `LandUse`    | `land_use`            | Broad land-use category                 |
| `OwnerName`  | `owner_name`          | Source-reported tax-lot owner           |
| `LotArea`    | `lot_area_sqft`       | Lot size                                |
| `BldgArea`   | `building_area_sqft`  | Total building floor area               |
| `NumBldgs`   | `number_of_buildings` | Structures associated with lot          |
| `NumFloors`  | `number_of_floors`    | Floors in tallest building              |
| `UnitsRes`   | `residential_units`   | Residential-unit denominator            |
| `UnitsTotal` | `total_units`         | Total residential/non-residential units |
| `YearBuilt`  | `year_built`          | Building-age analysis                   |
| `Latitude`   | `latitude`            | Approximate WGS84 point                 |
| `Longitude`  | `longitude`           | Approximate WGS84 point                 |
| `Version`    | `pluto_version`       | Source-release lineage                  |
| Geometry     | `geom`                | Tax-lot polygon                         |

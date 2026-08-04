# ADR-001: Preserve MapPLUTO geometry in EPSG:2263

## Status
Accepted

## Context
MapPLUTO geometry is supplied in NAD83 / New York Long Island
(ftUS), EPSG:2263. The application requires local spatial joins,
distance queries, tax-lot polygons, and later browser-map output.

## Decision
Store silver.tax_lots.geom as geometry(MultiPolygon, 2263).

## Consequences
- Local measurements use US survey feet.
- GiST indexing can operate directly on the source CRS.
- Browser-facing GeoJSON must be transformed to EPSG:4326.
- Latitude and longitude remain separate approximate WGS84 fields.
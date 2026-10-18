-- Caller must validate and hold staging stable before executing this statement.
-- PostgreSQL 17 MERGE reports real actions without relying on tuple internals.
WITH normalized AS (
    SELECT bbl::bigint::text AS bbl,
           borocode::smallint AS borough_code, btrim(borough) AS borough,
           block AS tax_block, lot AS tax_lot,
           nullif(btrim(address), '') AS address,
           CASE WHEN zipcode IS NULL OR zipcode = 0 THEN NULL ELSE zipcode::text END AS zip_code,
           nullif(cd, 0)::smallint AS community_district,
           nullif(btrim(bldgclass), '') AS building_class,
           nullif(btrim(landuse), '') AS land_use,
           nullif(btrim(ownername), '') AS owner_name,
           lotarea::bigint AS lot_area_sqft, bldgarea::bigint AS building_area_sqft,
           numbldgs AS number_of_buildings, numfloors::numeric(6,2) AS number_of_floors,
           unitsres AS residential_units, unitstotal AS total_units,
           CASE WHEN yearbuilt BETWEEN 1624 AND %(source_year)s
                THEN yearbuilt::smallint ELSE NULL END AS year_built,
           latitude, longitude, ST_Multi(shape)::geometry(MultiPolygon,2263) AS geom,
           btrim(version) AS pluto_version
    FROM staging.mappluto_source
), changed AS (
    MERGE INTO silver.tax_lots AS t
    USING normalized AS s ON t.bbl = s.bbl
    WHEN MATCHED AND
        ROW(t.borough_code, t.borough, t.tax_block, t.tax_lot, t.address,
            t.zip_code, t.community_district, t.building_class, t.land_use,
            t.owner_name, t.lot_area_sqft, t.building_area_sqft,
            t.number_of_buildings, t.number_of_floors, t.residential_units,
            t.total_units, t.year_built, t.latitude, t.longitude,
            ST_AsEWKB(t.geom), t.pluto_version)
        IS DISTINCT FROM
        ROW(s.borough_code, s.borough, s.tax_block, s.tax_lot, s.address,
            s.zip_code, s.community_district, s.building_class, s.land_use,
            s.owner_name, s.lot_area_sqft, s.building_area_sqft,
            s.number_of_buildings, s.number_of_floors, s.residential_units,
            s.total_units, s.year_built, s.latitude, s.longitude,
            ST_AsEWKB(s.geom), s.pluto_version)
    THEN UPDATE SET
        borough_code=s.borough_code, borough=s.borough,
        tax_block=s.tax_block, tax_lot=s.tax_lot, address=s.address,
        zip_code=s.zip_code, community_district=s.community_district,
        building_class=s.building_class, land_use=s.land_use, owner_name=s.owner_name,
        lot_area_sqft=s.lot_area_sqft, building_area_sqft=s.building_area_sqft,
        number_of_buildings=s.number_of_buildings, number_of_floors=s.number_of_floors,
        residential_units=s.residential_units, total_units=s.total_units,
        year_built=s.year_built, latitude=s.latitude, longitude=s.longitude,
        geom=s.geom, pluto_version=s.pluto_version,
        updated_at=statement_timestamp(), source_import_run_id=%(run_id)s
    WHEN NOT MATCHED THEN INSERT (
        bbl, borough_code, borough, tax_block, tax_lot, address, zip_code,
        community_district, building_class, land_use, owner_name, lot_area_sqft,
        building_area_sqft, number_of_buildings, number_of_floors, residential_units,
        total_units, year_built, latitude, longitude, geom, pluto_version,
        ingested_at, updated_at, source_import_run_id
    ) VALUES (
        s.bbl, s.borough_code, s.borough, s.tax_block, s.tax_lot, s.address, s.zip_code,
        s.community_district, s.building_class, s.land_use, s.owner_name, s.lot_area_sqft,
        s.building_area_sqft, s.number_of_buildings, s.number_of_floors, s.residential_units,
        s.total_units, s.year_built, s.latitude, s.longitude, s.geom, s.pluto_version,
        statement_timestamp(), statement_timestamp(), %(run_id)s
    )
    -- Unchanged matches do nothing. Absence is not a deletion instruction.
    RETURNING merge_action() AS action
)
SELECT count(*) FILTER (WHERE action = 'INSERT'),
       count(*) FILTER (WHERE action = 'UPDATE')
FROM changed;

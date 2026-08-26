DO $$
DECLARE
    v_run_id BIGINT;
    v_inserted BIGINT;
BEGIN
    -- 1. Create lineage/import-run record.
    INSERT INTO etl.import_runs (
        dataset_name,
        source_dataset_id,
        pipeline_version,
        source_version,
        status,
        raw_file_path,
        checksum_sha256,
        source_row_count,
        staged_row_count
    )
    VALUES (
        'MapPLUTO',
        NULL,
        'manual-mappluto-v1',
        '26v1',
        'STARTED',
        'data/bronze/mappluto/26v1/nyc_mappluto_26v1_fgdb.zip',
        'E3DD8DAD5085EF051A822410B04C57D6952D938526B3ABE61C02C3252BF44A02',
        856614,
        856614
    )
    RETURNING id INTO v_run_id;

    BEGIN
        -- 2. Transform staging -> trusted Silver.
        INSERT INTO silver.tax_lots (
            bbl,
            borough_code,
            borough,
            tax_block,
            tax_lot,
            address,
            zip_code,
            community_district,
            building_class,
            land_use,
            owner_name,
            lot_area_sqft,
            building_area_sqft,
            number_of_buildings,
            number_of_floors,
            residential_units,
            total_units,
            year_built,
            latitude,
            longitude,
            geom,
            pluto_version,
            ingested_at,
            updated_at,
            source_import_run_id
        )
        SELECT
            TRUNC(bbl)::BIGINT::TEXT,
            borocode::SMALLINT,
            BTRIM(borough),
            block,
            lot,

            NULLIF(BTRIM(address), ''),

            CASE
                WHEN zipcode IS NULL OR zipcode = 0 THEN NULL
                ELSE zipcode::TEXT
            END,

            NULLIF(cd, 0)::SMALLINT,

            NULLIF(BTRIM(bldgclass), ''),
            NULLIF(BTRIM(landuse), ''),
            NULLIF(BTRIM(ownername), ''),

            lotarea::BIGINT,
            bldgarea::BIGINT,
            numbldgs,
            numfloors::NUMERIC,
            unitsres,
            unitstotal,

            CASE
                WHEN yearbuilt BETWEEN 1624 AND %(source_year)s
                    THEN yearbuilt::SMALLINT
                ELSE NULL
            END

            latitude,
            longitude,

            ST_Multi(shape)::geometry(MultiPolygon, 2263),

            BTRIM(version),

            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,

            v_run_id

        FROM staging.mappluto_source;

        GET DIAGNOSTICS v_inserted = ROW_COUNT;

        -- 3. Do not accept an incomplete promotion.
        IF v_inserted <> 856614 THEN
            RAISE EXCEPTION
                'Expected 856614 rows but inserted %',
                v_inserted;
        END IF;

        -- 4. Mark import successful.
        UPDATE etl.import_runs
        SET
            status = 'SUCCEEDED',
            completed_at = CURRENT_TIMESTAMP,
            inserted_count = v_inserted,
            updated_count = 0,
            rejected_count = 0,
            error_message = NULL
        WHERE id = v_run_id;

        RAISE NOTICE
            'MapPLUTO import run % succeeded with % rows',
            v_run_id,
            v_inserted;

    EXCEPTION
        WHEN OTHERS THEN
            UPDATE etl.import_runs
            SET
                status = 'FAILED',
                completed_at = CURRENT_TIMESTAMP,
                inserted_count = 0,
                updated_count = 0,
                error_message = SQLERRM
            WHERE id = v_run_id;

            RAISE WARNING
                'MapPLUTO Silver load failed: %',
                SQLERRM;
    END;
END $$;
-- NULL means invalid for required checks. Group counts can overlap; rejected
-- counts each invalid row once. All copies of a duplicated BBL are rejected.
WITH checked AS (
    SELECT
        (bbl BETWEEN 1000000000 AND 5999999999 AND bbl = trunc(bbl)
         AND bbl = borocode::numeric * 1000000000 + block::numeric * 10000 + lot
         AND borocode BETWEEN 1 AND 5 AND block BETWEEN 0 AND 99999
         AND lot BETWEEN 0 AND 9999
         AND btrim(borough) = CASE borocode
             WHEN 1 THEN 'MN' WHEN 2 THEN 'BX' WHEN 3 THEN 'BK'
             WHEN 4 THEN 'QN' WHEN 5 THEN 'SI' END) IS TRUE AS identity_ok,
        count(*) OVER (PARTITION BY bbl) = 1 AS unique_ok,
        (shape IS NOT NULL AND NOT ST_IsEmpty(shape)
         AND ST_GeometryType(shape) IN ('ST_Polygon', 'ST_MultiPolygon')
         AND ST_SRID(shape) = %(srid)s AND ST_NDims(shape) = 2
         AND ST_IsValid(shape, 0)) IS TRUE AS geometry_ok,
        (btrim(version) = %(release)s) IS TRUE AS release_ok,
        ((lotarea IS NULL OR lotarea >= 0)
         AND (bldgarea IS NULL OR bldgarea >= 0)
         AND (numbldgs IS NULL OR numbldgs BETWEEN 0 AND 2147483647)
         AND (unitsres IS NULL OR unitsres BETWEEN 0 AND 2147483647)
         AND (unitstotal IS NULL OR unitstotal BETWEEN 0 AND 2147483647)
         AND (numfloors IS NULL OR numfloors BETWEEN 0 AND 9999.99)
         AND (cd IS NULL OR cd BETWEEN 0 AND 32767)
         AND (zipcode IS NULL OR zipcode = 0 OR zipcode BETWEEN 10000 AND 99999)
         AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)
         AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)) IS TRUE AS attributes_ok
    FROM staging.mappluto_source
)
SELECT count(*),
       count(*) FILTER (WHERE identity_ok AND unique_ok AND geometry_ok AND release_ok AND attributes_ok),
       jsonb_build_object(
           'invalid_identity', count(*) FILTER (WHERE NOT identity_ok),
           'duplicate_identity_rows', count(*) FILTER (WHERE NOT unique_ok),
           'invalid_geometry', count(*) FILTER (WHERE NOT geometry_ok),
           'wrong_release', count(*) FILTER (WHERE NOT release_ok),
           'invalid_attributes', count(*) FILTER (WHERE NOT attributes_ok)
       )
FROM checked;

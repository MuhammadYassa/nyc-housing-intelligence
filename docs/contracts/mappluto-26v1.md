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

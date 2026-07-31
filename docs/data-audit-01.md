MapPLUTO / PLUTO sample
- Sample size: 9 rows
- Number of columns: 108
- Row grain: Row grain: generally one record per tax lot; condominium unit lots are aggregated into one record for the condominium complex or billing lot.
- Candidate primary key: BBL
- Exact BBL field: BBL
- BBL representation: 10-digit identifier; store as text
- Address field: address
- Borough fields: borough and borocode
- Residential units field: unitsres
- Total units field: unitstotal
- Building count field: numbldgs
- Year-built field: yearbuilt
- Version: 26v1
- Multiple buildings on one lot: yes; one sample has numbldgs = 2
- Latitude/longitude: present
- Tax-lot polygon geometry: not available in this text sample
- Geometry type and CRS: must inspect the geographic file in QGIS
- Publication date: 05/28/2026
- Missing BBLs in full dataset: no
- Major releases: quarterly; all fields may be updated
- Minor releases: monthly between major releases; primarily zoning fields are updated

HPD Violations sample
- Sample size: 48 records
- Row grain: one individual violation record
- Candidate primary key: violationid
- Related notice identifier: novid
- Property identifiers: bbl, bin, buildingid
- Registration identifier: registrationid
- Classes observed: A, B, C, I
- Broad status field: violationstatus
- Detailed status field: currentstatus
- Relevant dates: inspectiondate, approveddate,
  originalcorrectbydate, originalcertifybydate,
  certifieddate, novissueddate, currentstatusdate,
  :created_at, :updated_at
- Coordinates: latitude and longitude
- Multiple violations per BBL: expected and observed
- Missing fields: some optional fields are absent from some objects
- Full-dataset uniqueness and missing-value rates: not yet determined
- Broad open/closed field: violationstatus
- Allowed broad values: Open, Close
- Detailed state field: currentstatus
- Detailed state identifier: currentstatusid
- Open means the violation remains active in HPD records; it does not necessarily prove that the physical condition remains uncorrected.
- Publishing frequency: daily
- Data change frequency: daily
- Daily updates include new violations and status changes to existing violations
- Historical coverage limitation: base dataset includes violations that were open as of October 1, 2012, followed by later activity
 
QGIS Audit:
- Storage: OpenFileGDB
- Provider: ogr
- Geometry Type: Polygon (MultiPolygon)
- CRS name: NAD83 / New York Long Island (ftUS)
- CRS authority/code: EPSG:2263
- CRS units: feet (US survey)
- Extent: 913128.9263725280761719,120048.9859609603881836 : 1067335.9512643814086914,272811.1829943656921387
- BBL field name: BBL
- BBL field type: Real
- Version field name: Version
- Version value: 26v1
- Number-of-buildings field: NumbBldgs
- Residential-units field: UnitsRes
- Multiple buildings per tax lot observed: Yes
- Example BBL: 4163500400
- Number of buildings: 1862
- Blank/null BBL count: 0
- Total feature count: 856614
- Null or empty geometry count: 0

Known-property test:
- BBL: 2054800111
- Expected address: 761 CLARENCE AVENUE
- QGIS address: 761 CLARENCE AVENUE
- Polygon appeared in expected borough: Yes
- Notes: Appeared Correctly on Clarence Avenue
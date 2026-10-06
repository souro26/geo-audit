# geo-audit

**Audit heterogeneous geospatial datasets for common data-quality and spatial-consistency problems before they enter downstream geospatial ML pipelines.**

## The Problem

Geospatial data in exploration and earth science workflows often comes from multiple sources:
- Field survey CSVs with latitude/longitude columns
- Historical exploration datasets with different column naming conventions
- GeoJSON files from geological mapping systems
- Planar coordinate datasets (UTM, local grids) without CRS metadata

Before training ML models or doing spatial analysis, engineers need to know:
- Do these datasets actually contain usable coordinates?
- Are coordinate values valid (within -90..90 / -180..180)?
- Are there missing spatial records?
- Are there duplicate locations?
- Are datasets using different coordinate reference systems?
- What geographic area does each dataset cover?
- How much do datasets overlap spatially?
- Which columns have substantial missingness?
- Are there obvious schema/type inconsistencies?

`geo-audit` answers these questions with a single command.

## Installation

```bash
pip install -e .
```

Requires Python 3.10+.

## Quick Start

```bash
# Terminal report (default)
geo-audit ./data/

# JSON output to stdout
geo-audit ./data/ --format json

# JSON output to file
geo-audit ./data/ --format json --output report.json
```

## Supported Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| CSV | `.csv` | Coordinate columns auto-detected |
| GeoJSON | `.geojson`, `.json` | Geometry extracted directly |

## Example

```bash
$ geo-audit examples/data/
```

```
=== geo-audit Report ===
Generated: 2026-10-06T13:16:33.140602

            Executive Summary             
 Datasets scanned                      4  
 Total records                         35 
 Total columns                         23 
 Warnings                              4  
 Errors                                0  
 Datasets with geographic coordinates  2  
 Datasets with spatial extent          3  

                       Dataset Inventory                       
+-------------------------------------------------------------+
| File                    | Format  | Rows | Columns |   Size |
|-------------------------+---------+------+---------+--------|
| exploration_samples.csv | CSV     |   12 |       7 | 0.7 KB |
| geology.geojson         | GEOJSON |    5 |       4 | 1.5 KB |
| historical_surveys.csv  | CSV     |   10 |       6 | 0.5 KB |
| planar_samples.csv      | CSV     |    8 |       6 | 0.4 KB |
+-------------------------------------------------------------+

               Geographic Coordinate Quality (explicit lat/lon)                
+-----------------------------------------------------------------------------+
|         | Lat     | Lon     |         |         |  Valid | Missing | Inval� |
| Dataset | Column  | Column  | Method  | Confid� |      % |       % |      % |
|---------+---------+---------+---------+---------+--------+---------+--------|
| explor� | latitu� | longit� | explic� |     95% |  66.7% |   16.7% |  16.7% |
| geolog� | �       | �       | none    |      0% |      � |       � |      � |
| histor� | lat     | lon     | explic� |     95% | 100.0% |    0.0% |   0.0% |
| planar� | �       | �       | none    |      0% |      � |       � |      � |
+-----------------------------------------------------------------------------+

       Planar/Unknown Coordinates (x/y, easting/northing - CRS unknown)        
+-----------------------------------------------------------------------------+
| Dataset         | X Column | Y Column | Method          | Count | Missing % |
|-----------------+----------+----------+-----------------+-------+-----------|
| exploration_sa� | �        | �        | none            |     0 |         � |
| geology.geojson | �        | �        | none            |     0 |         � |
| historical_sur� | �        | �        | none            |     0 |         � |
| planar_samples� | easting  | northing | planar_heurist� |     8 |     12.5% |
+-----------------------------------------------------------------------------+

             Column Missingness (columns with >5% missing)              
+----------------------------------------------------------------------+
| Dataset                 | Column    | Type    | Missing % | Severity |
|-------------------------+-----------+---------+-----------+----------|
| exploration_samples.csv | latitude  | float64 |      8.3% |   WARN   |
| exploration_samples.csv | longitude | float64 |      8.3% |   WARN   |
| exploration_samples.csv | notes     | str     |     41.7% |   HIGH   |
| planar_samples.csv      | easting   | float64 |     12.5% |   WARN   |
| planar_samples.csv      | northing  | float64 |     12.5% |   WARN   |
+----------------------------------------------------------------------+

No schema inconsistencies detected

                       CRS / Spatial Reference                       
+-------------------------------------------------------------------+
| Dataset                 | CRS                    | Geometry Types |
|-------------------------+------------------------+----------------|
| exploration_samples.csv | unknown / not declared | �              |
| geology.geojson         | EPSG:4326              | Point          |
| historical_surveys.csv  | unknown / not declared | �              |
| planar_samples.csv      | unknown / not declared | �              |
+-------------------------------------------------------------------+

                       Spatial Coverage (Bounding Boxes)                       
+-----------------------------------------------------------------------------+
| Dataset                 |    Min Lat |    Max Lat |    Min Lon |    Max Lon |
|-------------------------+------------+------------+------------+------------|
| exploration_samples.csv | -23.472300 | -23.456700 | 134.123400 | 134.139000 |
| geology.geojson         | -23.464500 | -23.456700 | 134.123400 | 134.131200 |
| historical_surveys.csv  | -23.474500 | -23.456700 | 134.123400 | 134.141200 |
| planar_samples.csv      |          � |          � |          � |          � |
+-----------------------------------------------------------------------------+

            Cross-Dataset Spatial Overlap (Bounding Box)            
+------------------------------------------------------------------+
| Dataset A               | Dataset B              | Boxes Overlap |
|-------------------------+------------------------+---------------|
| exploration_samples.csv | geology.geojson        |      YES      |
| exploration_samples.csv | historical_surveys.csv |      YES      |
| geology.geojson         | historical_surveys.csv |      YES      |
+------------------------------------------------------------------+

+--------------------------------- Warnings ----------------------------------+
| exploration_samples.csv: 16.7% missing coordinates                          |
| exploration_samples.csv: 16.7% invalid coordinates                          |
| exploration_samples.csv: 20.0% exact duplicate locations                    |
| planar_samples.csv: Planar coordinates (easting/northing): 12.5% missing    |
| exploration_samples.csv: Only 66.7% records have valid coordinates          |
| exploration_samples.csv: 2 exact duplicate locations (20.0%)                |
| exploration_samples.csv: Column 'notes' has 41.7% missing values            |
+-----------------------------------------------------------------------------+
```

## What Each Audit Checks

### 1. Dataset Discovery
- Recursively finds `.csv`, `.geojson`, `.json` files
- Reports: filename, format, row count, columns, file size
- Gracefully handles malformed files (reports parse errors per dataset)

### 2. Coordinate Detection (CSV only)
- **Geographic coordinates**: Explicit latitude/longitude column names only
  - Patterns: `latitude`/`lat`/`lat_dd`/..., `longitude`/`lon`/`lng`/`long`/...
  - High confidence (0.95), validated as WGS84 lat/lon
- **Planar coordinates**: Generic x/y, easting/northing pairs
  - Reported separately with `planar_heuristic` method
  - **Not** validated as lat/lon (CRS unknown)
  - No geographic bounding box generated

### 3. Coordinate Validation
For geographic (lat/lon) coordinates:
- Latitude in [-90, 90]
- Longitude in [-180, 180]
- Reports: valid %, missing %, invalid %

### 4. Duplicate Detection
- Exact duplicate coordinate pairs (geographic only)
- Reports count and percentage
- Phrased as "worth reviewing" not "errors"

### 5. Missingness Analysis
Per-column missingness with severity thresholds:
- **INFO**: < 5%
- **WARN**: 5–20%
- **HIGH**: > 20%

### 6. Schema Inspection
Cross-dataset column comparison by normalized name:
- Type mismatches (e.g., `float64` vs `object`) → WARNING
- Name variations (e.g., `sample_id` vs `Sample_ID`) → INFO

### 7. CRS / Spatial Reference
- GeoJSON: Reports CRS from file metadata (e.g., `EPSG:4326`)
- CSV lat/lon: Reports "unknown / not declared" (treated as WGS84 for validation)
- Planar: Reports "unknown / not declared" — no CRS assumption made

### 8. Spatial Extent
- Geographic bounding boxes (min/max lat/lon) for:
  - CSV with detected lat/lon columns
  - GeoJSON (from geometry)
- **No** bounding box for planar coordinates (CRS unknown)

### 9. Cross-Dataset Spatial Overlap
- Bounding box overlap: YES/NO
- Only compares datasets with geographic bounding boxes
- Non-overlapping boxes are **not** warned — may be perfectly valid

## Output Formats

| Format | Description |
|--------|-------------|
| `terminal` (default) | Human-readable Rich tables |
| `json` | Structured JSON for automation |

```bash
# Save JSON report
geo-audit ./data/ --format json --output audit.json
```

## Demo Data

The repository includes synthetic exploration-style data in `examples/data/`:

| File | Description | Issues |
|------|-------------|--------|
| `exploration_samples.csv` | 12 samples with lat/lon | Missing coords, invalid coords (-95, 190), duplicates, 41.7% missing in notes |
| `historical_surveys.csv` | 10 historical surveys | Clean lat/lon, different column names (`lat`/`lon` vs `latitude`/`longitude`) |
| `geology.geojson` | 5 Point features | EPSG:4326 CRS declared |
| `planar_samples.csv` | 8 samples with easting/northing | Planar coords (CRS unknown), 12.5% missing |

Run the demo:
```bash
geo-audit examples/data/
```

## Limitations

- **v0.1 scope**: CSV and GeoJSON only; Point geometries in GeoJSON
- No raster / imagery support
- No coordinate transformation — planar coordinates remain planar
- No near-duplicate detection (exact duplicates only)
- No spatial join / exact feature overlap (bounding box only)
- No HTML report yet
- CRS handling follows GeoJSON spec (assumes WGS84 if absent) but does not validate

## Design Philosophy

> "Surface things an engineer should investigate before trusting a geospatial dataset."

- **No false precision**: Bounding box overlap ≠ feature overlap
- **No invented metadata**: Unknown CRS stays unknown
- **Actionable diagnostics**: "16.7% missing coordinates" not "Dataset quality is poor"
- **Conservative warnings**: Only flag things worth human review

## Extending

The internal models (`DatasetInfo`, `CoordinateInfo`, `AuditReport`) are designed for future extensions:
- Raster datasets
- Satellite imagery metadata
- Richer CRS handling (pyproj integration)
- Spatial clustering / leakage checks
- Geospatial feature validation
- Data lineage tracking

## License

MIT
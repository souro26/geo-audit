# geo-audit

`geo-audit` is a command-line tool for auditing raw geospatial datasets before ingestion into spatial analysis, GIS workflows, or machine learning pipelines. It inspects CSV and GeoJSON files in a directory to identify coordinate anomalies, missing spatial metadata, attribute missingness, exact duplicate locations, and cross-dataset bounding box overlaps without modifying source data.

## Purpose

Geospatial data collected from field surveys, legacy archives, and third-party GIS exports frequently contains quality defects—such as out-of-range latitude/longitude coordinates, unprojected planar coordinates lacking CRS definitions, silent duplicate coordinates, and missing values across attribute columns. `geo-audit` runs static health checks across all datasets in a target directory to surface critical defects and risk levels in a single pass.

## Installation

Requires Python 3.10 or higher.

```bash
git clone https://github.com/souro26/geo-audit
cd geo-audit
pip install -e .
```

## Quick Start

Scan a directory of geospatial files for a human-readable terminal report:

```bash
geo-audit data/
```

Generate machine-readable JSON output for automated pipelines:

```bash
geo-audit data/ --format json
```

Save JSON directly to a file (suppresses terminal progress):

```bash
geo-audit data/ --format json --output report.json
```

## Audit Capabilities

- **Geographic Coordinate Validation**: Auto-detects `latitude`/`longitude` columns (including variants like `lat`/`lon`/`lng`), coerces non-numeric entries, and flags values outside valid ranges ([-90, 90] and [-180, 180]).
- **Planar Coordinate Inspection**: Identifies planar coordinate pairs (`easting`/`northing`, `x`/`y`) and flags missing values. Planar coordinates are reported separately because their Coordinate Reference System (CRS) is unknown.
- **Duplicate Location Detection**: Identifies exact duplicate coordinate pairs across records within CSV datasets.
- **Attribute Missingness Profiling**: Checks column-level completeness. Attribute columns with missingness exceeding 5% are flagged (`WARN` at 5-20%, `HIGH` above 20%). Coordinate columns are excluded from column missingness to prevent duplicate reporting.
- **CRS and Bounding Box Analysis**: Extracts declared CRS from GeoJSON datasets and computes spatial bounding boxes for geographic datasets to evaluate spatial coverage and cross-dataset bounding box overlaps.
- **Cross-Dataset Schema Comparison**: Identifies normalized column name matches and data type discrepancies across datasets.

## Dataset Readiness Levels

Every scanned dataset is assigned an overall readiness status based on the highest severity finding detected:

- **READY**: No blocking or moderate issues detected by active checks.
- **REVIEW**: Moderate-severity findings detected (e.g., 5-20% missingness, duplicate locations, missing planar coordinates).
- **HIGH RISK**: High-severity findings detected (e.g., >20% missing or invalid geographic coordinates, high column missingness).
- **ERROR**: Unparseable files or critical dataset structural failure.

## Demo Data

The included `data/` directory contains synthetic test cases demonstrating common data issues:

| File | Description | Primary Findings |
|---|---|---|
| `exploration_samples.csv` | 12 sample points | Out-of-range coordinates, missing lat/lon, 41.7% missing notes, duplicate locations |
| `historical_surveys.csv` | 10 survey points | Clean dataset using `lat`/`lon` column headers |
| `geology.geojson` | 5 Point geometries | Clean GeoJSON dataset with EPSG:4326 |
| `planar_samples.csv` | 8 sample points | Easting/northing planar coordinates with 12.5% missing values |

Run the demo against the included data:

```bash
geo-audit data/
```

## Scope and Limitations

- **Supported Formats**: CSV (`.csv`) and GeoJSON (`.geojson`, `.json`).
- **Duplicate Detection**: Performs exact coordinate pair matching; near-duplicate spatial clustering is not performed.
- **Spatial Overlap**: Evaluates bounding box intersection; polygon geometry intersections are out of scope.
- **CRS Transformations**: Does not attempt automatic CRS inference or coordinate re-projection.

## License

MIT
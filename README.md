# geo-audit

A command-line tool for auditing geospatial datasets before they go anywhere near a pipeline.

Geospatial data from field surveys, historical archives, and GIS exports tends to arrive messy — mismatched coordinate columns, undeclared CRS, duplicate locations, missing values scattered across the schema. `geo-audit` scans a directory of CSV and GeoJSON files and surfaces those problems in one pass, without modifying anything.

## Installation

```bash
git clone https://github.com/souro26/geo-audit
cd geo-audit
pip install -e .
```

Requires Python 3.10+.

## Usage

Point it at a directory and it scans everything inside recursively:

```bash
geo-audit ./data/
```

For structured output — useful if you want to pipe results into another tool or store them:

```bash
geo-audit ./data/ --format json
geo-audit ./data/ --format json --output report.json
```

## What it checks

For each dataset, `geo-audit` reports row count, column count, and file size. Beyond that:

**Coordinate quality** — For CSVs, it detects geographic coordinate columns by name (`latitude`/`lat`, `longitude`/`lon`, etc.) and validates that values fall within [-90, 90] and [-180, 180]. Planar columns like `easting`/`northing` are detected separately and reported without range validation, since their CRS is unknown. It reports valid %, missing %, and invalid % for each dataset.

**Duplicates** — Exact duplicate coordinate pairs are counted and reported as a percentage. These are flagged for review, not treated as hard errors.

**Missingness** — Every column is checked for missing values. Anything above 5% gets reported with a severity level: `WARN` (5-20%) or `HIGH` (>20%).

**Schema consistency** — Column names are normalized across datasets and compared. Type mismatches (e.g. `float64` in one file, `object` in another) are flagged as warnings.

**CRS and spatial extent** — GeoJSON files report their declared CRS. CSVs with detected lat/lon get a bounding box; planar datasets do not, since projecting without a known CRS would be wrong. Bounding box overlap across datasets is computed and reported.

## Example output

```bash
$ geo-audit examples/data/
```

```
=== geo-audit Report ===
Generated: 2026-10-06T13:16:33

Executive Summary
  Datasets scanned                      4
  Total records                         35
  Total columns                         23
  Warnings                              4
  Errors                                0
  Datasets with geographic coordinates  2
  Datasets with spatial extent          3

Dataset Inventory
  File                      Format   Rows  Columns    Size
  exploration_samples.csv   CSV        12        7  0.7 KB
  geology.geojson           GEOJSON     5        4  1.5 KB
  historical_surveys.csv    CSV        10        6  0.5 KB
  planar_samples.csv        CSV         8        6  0.4 KB

Geographic Coordinate Quality (explicit lat/lon)
  Dataset                   Lat Col    Lon Col    Method    Confidence  Valid %  Missing %  Invalid %
  exploration_samples.csv   latitude   longitude  explicit       95%    66.7%      16.7%      16.7%
  geology.geojson           --         --         none            0%    --         --         --
  historical_surveys.csv    lat        lon        explicit       95%   100.0%       0.0%       0.0%
  planar_samples.csv        --         --         none            0%    --         --         --

Column Missingness (columns with >5% missing)
  Dataset                   Column     Type     Missing %  Severity
  exploration_samples.csv   latitude   float64      8.3%   WARN
  exploration_samples.csv   longitude  float64      8.3%   WARN
  exploration_samples.csv   notes      str         41.7%   HIGH
  planar_samples.csv        easting    float64     12.5%   WARN
  planar_samples.csv        northing   float64     12.5%   WARN

CRS / Spatial Reference
  Dataset                   CRS                     Geometry Types
  exploration_samples.csv   unknown / not declared  --
  geology.geojson           EPSG:4326               Point
  historical_surveys.csv    unknown / not declared  --
  planar_samples.csv        unknown / not declared  --

Warnings
  exploration_samples.csv: 16.7% missing coordinates
  exploration_samples.csv: 16.7% invalid coordinates
  exploration_samples.csv: 20.0% exact duplicate locations
  planar_samples.csv: Planar coordinates (easting/northing): 12.5% missing
```

## Demo data

`examples/data/` contains four synthetic files that cover the common problem cases:

| File | Description |
|------|-------------|
| `exploration_samples.csv` | 12 samples with lat/lon — has missing coords, an out-of-range value (-95, 190), duplicates, and 41.7% missing in the `notes` column |
| `historical_surveys.csv` | 10 clean surveys using `lat`/`lon` instead of `latitude`/`longitude` |
| `geology.geojson` | 5 Point features with EPSG:4326 declared |
| `planar_samples.csv` | 8 samples with easting/northing (CRS unknown), 12.5% missing |

## Supported formats

CSV and GeoJSON (`.geojson`, `.json`). Raster, shapefile, and other formats are out of scope for now.

## Limitations

This is a v0.1 tool. It does exact duplicate detection only (no spatial clustering or near-duplicate checks), bounding box overlap only (not feature-level intersection), and no coordinate transformation. Planar datasets are reported without any CRS assumption. There is no HTML output yet.

## License

MIT

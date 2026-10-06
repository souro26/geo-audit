# geo-audit

A geospatial data quality and readiness audit tool for identifying data issues before downstream geospatial analysis and ML.

Geospatial data from field surveys, historical archives, and GIS exports tends to arrive messy — mismatched coordinate columns, undeclared CRS, duplicate locations, missing values scattered across the schema. `geo-audit` scans a directory of CSV and GeoJSON files and surfaces those problems in one pass, without modifying anything.

## Installation

```bash
git clone https://github.com/souro26/geo-audit
cd geo-audit
pip install -e .
```

Requires Python 3.10+.

## Quick Start

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

## Output format

The terminal report is decision-oriented:

1. **Overall status** — READY / NEEDS REVIEW / ERROR
2. **Overall assessment** — concise summary of dataset readiness
3. **Top priorities** — actionable findings with why-it-matters and recommended actions
4. **Dataset readiness** — compact table showing each dataset's status (READY / REVIEW / HIGH RISK / ERROR)
5. **Detailed evidence** — full technical tables for verification
6. **Technical notes** — limitations and caveats

For structured output:

```bash
geo-audit ./data/ --format json
geo-audit ./data/ --format json --output report.json
```

The JSON contains structured findings, dataset readiness, and full technical evidence.

## Example terminal output

```bash
$ geo-audit data/
```

```
GEO-AUDIT
DATA READINESS REPORT

STATUS: NEEDS REVIEW

4 datasets scanned · 35 records · 23 columns

8 findings require attention
0 critical · 2 high · 6 medium · 0 low

OVERALL ASSESSMENT
------------------------------------------------------------

NOT READY FOR DOWNSTREAM SPATIAL ML

2 dataset(s) have no flagged issues.
1 dataset(s) require review.
1 dataset(s) are HIGH RISK.

HIGH RISK:
  exploration_samples.csv

REVIEW:
  planar_samples.csv

READY:
  geology.geojson
  historical_surveys.csv

TOP PRIORITIES
------------------------------------------------------------

1. HIGH   exploration_samples.csv
   Unusable geographic coordinates
   33.3% of records have unusable coordinates (16.7% missing, 16.7% invalid).
   Why it matters: Records with missing or invalid latitude/longitude cannot be used in spatial joins, mapping, spatial aggregation, or downstream geospatial ML.
   Recommended action: Inspect and correct or remove the affected records before downstream spatial processing.

2. HIGH   exploration_samples.csv
   High missingness in column 'notes'
   Column 'notes' has 41.7% missing values.
   Why it matters: High missingness in important columns can bias analysis and reduce statistical power.
   Recommended action: Assess whether the column is critical for downstream use. Consider imputation, removal, or accepting the reduced sample size.

...

DATASET READINESS
------------------------------------------------------------
+-----------------------------+--------------+----------+------------------+
| Dataset                     | Status       | Findings | Highest Severity |
+-----------------------------+--------------+----------+------------------+
| exploration_samples.csv     | HIGH RISK    | 5        | HIGH             |
| geology.geojson             | READY        | 0        | INFO             |
| historical_surveys.csv      | READY        | 0        | INFO             |
| planar_samples.csv          | REVIEW       | 3        | MEDIUM           |
+-----------------------------+--------------+----------+------------------+

... detailed evidence tables ...
```

## Demo data

`data/` contains four synthetic files that cover the common problem cases:

| File | Description |
|------|-------------|
| `exploration_samples.csv` | 12 samples with lat/lon — has missing coords, an out-of-range value (-95, 190), duplicates, and 41.7% missing in the `notes` column |
| `historical_surveys.csv` | 10 clean surveys using `lat`/`lon` instead of `latitude`/`longitude` |
| `geology.geojson` | 5 Point features with EPSG:4326 declared |
| `planar_samples.csv` | 8 samples with easting/northing (CRS unknown), 12.5% missing |

Run the demo:
```bash
geo-audit data/
```

## Supported formats

CSV and GeoJSON (`.geojson`, `.json`). Raster, shapefile, and other formats are out of scope for now.

## Readiness semantics

| Status | Meaning |
|--------|---------|
| **READY** | No blocking issues detected by the checks currently implemented. |
| **REVIEW** | Moderate-severity findings present; investigate before downstream use. |
| **HIGH RISK** | High-severity findings present; resolve before downstream use. |
| **ERROR** | Parse errors or critical issues; dataset cannot be processed. |

**READY does NOT mean:**
- The dataset is guaranteed suitable for downstream ML.
- The data is "correct" or "clean" in an absolute sense.

**READY means:**
- No blocking issues were detected by the checks currently implemented.

## JSON output

When using `--format json`, stdout contains only valid JSON. No progress messages or Rich formatting. The JSON includes:

- `summary` — dataset counts, record counts, findings by severity
- `findings` — structured findings with severity, category, title, details, why_it_matters, recommended_action
- `dataset_readiness` — per-dataset status, finding count, highest severity
- `datasets` — full technical evidence for each dataset
- `cross_dataset_overlaps` — bounding box overlap results
- `generated_at` — ISO timestamp

```bash
geo-audit ./data/ --format json > report.json
python -c "import json; json.load(open('report.json')); print('VALID JSON')"
```

## Limitations

This is a v0.1 tool. It does exact duplicate detection only (no spatial clustering or near-duplicate checks), bounding box overlap only (not feature-level intersection), and no coordinate transformation. Planar datasets are reported without any CRS assumption. There is no HTML output yet.

## License

MIT
"""Data loaders for CSV and GeoJSON."""

from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from geo_audit.models import BoundingBox, ColumnProfile, FileFormat, GeometryType


def load_csv(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Load CSV file, return DataFrame and parse errors."""
    errors = []
    try:
        df = pd.read_csv(path, low_memory=False)
    except pd.errors.ParserError as e:
        errors.append(f"CSV parse error: {e}")
        return pd.DataFrame(), errors
    except UnicodeDecodeError as e:
        errors.append(f"Encoding error: {e}")
        return pd.DataFrame(), errors
    except Exception as e:
        errors.append(f"Unexpected error loading CSV: {e}")
        return pd.DataFrame(), errors
    return df, errors


def load_geojson(path: Path) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Load GeoJSON file, return GeoDataFrame and parse errors."""
    errors = []
    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        errors.append(f"GeoJSON parse error: {e}")
        return gpd.GeoDataFrame(), errors
    return gdf, errors


def load_dataset(path: Path, format: FileFormat) -> tuple[Any, list[str]]:
    """Load dataset based on format."""
    if format == FileFormat.CSV:
        return load_csv(path)
    elif format == FileFormat.GEOJSON:
        return load_geojson(path)
    else:
        return None, [f"Unsupported format: {format}"]


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """Generate column profiles for a DataFrame."""
    profiles = []
    for col in df.columns:
        series = df[col]
        missing_count = int(series.isna().sum())
        total = len(series)
        missing_pct = (missing_count / total * 100) if total > 0 else 0.0
        unique_count = int(series.nunique())
        dtype = str(series.dtype)
        sample_values = series.dropna().head(5).tolist()

        profiles.append(ColumnProfile(
            name=col,
            dtype=dtype,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            unique_count=unique_count,
            sample_values=sample_values,
        ))
    return profiles


def infer_geometry_types(gdf: gpd.GeoDataFrame) -> list[GeometryType]:
    """Extract unique geometry types from GeoDataFrame."""
    if gdf.empty or gdf.geometry.isna().all():
        return []

    geom_types = gdf.geometry.geom_type.dropna().unique()
    result = []
    for gt in geom_types:
        try:
            result.append(GeometryType(gt))
        except ValueError:
            result.append(GeometryType.UNKNOWN)
    return result


def calculate_bounding_box(gdf: gpd.GeoDataFrame) -> BoundingBox | None:
    """Calculate bounding box from GeoDataFrame."""
    if gdf.empty or gdf.geometry.isna().all():
        return None

    # Get total bounds (minx, miny, maxx, maxy) - in GeoPandas this is (lon, lat)
    bounds = gdf.total_bounds
    if bounds is None or len(bounds) != 4:
        return None

    min_lon, min_lat, max_lon, max_lat = bounds
    return BoundingBox(
        min_lat=float(min_lat),
        max_lat=float(max_lat),
        min_lon=float(min_lon),
        max_lon=float(max_lon),
    )


def calculate_bounding_box_from_coords(
    df: pd.DataFrame, lat_col: str, lon_col: str
) -> BoundingBox | None:
    """Calculate bounding box from coordinate columns."""
    valid = df.dropna(subset=[lat_col, lon_col])
    if valid.empty:
        return None

    # Filter valid lat/lon ranges
    valid = valid[
        (valid[lat_col] >= -90) & (valid[lat_col] <= 90) &
        (valid[lon_col] >= -180) & (valid[lon_col] <= 180)
    ]
    if valid.empty:
        return None

    return BoundingBox(
        min_lat=float(valid[lat_col].min()),
        max_lat=float(valid[lat_col].max()),
        min_lon=float(valid[lon_col].min()),
        max_lon=float(valid[lon_col].max()),
    )

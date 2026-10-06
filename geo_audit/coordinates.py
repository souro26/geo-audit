"""Coordinate detection and validation."""


import pandas as pd

from geo_audit.models import CoordinateInfo, PlanarCoordinateInfo

LAT_PATTERNS = [
    "latitude", "lat", "lat_dd", "lat_ddm", "lat_dms",
    "y_lat", "ycoord_lat", "gps_lat", "gps_latitude",
]

LON_PATTERNS = [
    "longitude", "lon", "lng", "long",
    "lon_dd", "lon_ddm", "lon_dms",
    "x_lon", "xcoord_lon", "gps_lon", "gps_longitude",
]

PLANAR_PATTERNS = [
    ("x", "y"),
    ("x_coord", "y_coord"),
    ("xcoordinate", "ycoordinate"),
    ("easting", "northing"),
]


def detect_coordinate_columns(df: pd.DataFrame) -> CoordinateInfo:
    """Detect latitude/longitude columns in a DataFrame.

    Only explicit latitude/longitude column names are treated as geographic coordinates.
    Generic x/y or easting/northing columns are NOT assumed to be lat/lon.
    """
    cols_lower = {c.lower().strip(): c for c in df.columns}
    info = CoordinateInfo()

    lat_col = _find_column(cols_lower, LAT_PATTERNS)
    lon_col = _find_column(cols_lower, LON_PATTERNS)

    if lat_col and lon_col:
        info.lat_column = lat_col
        info.lon_column = lon_col
        info.detection_method = "explicit_lat_lon"
        info.confidence = 0.95
        _validate_coordinates(df, info)

    return info


def detect_planar_coordinates(df: pd.DataFrame) -> PlanarCoordinateInfo | None:
    """Detect planar coordinate columns (x/y, easting/northing).

    These are NOT validated as lat/lon since their CRS is unknown.
    Returns info about the columns if found.
    """
    cols_lower = {c.lower().strip(): c for c in df.columns}

    for x_pat, y_pat in PLANAR_PATTERNS:
        x_col = _find_column(cols_lower, [x_pat])
        y_col = _find_column(cols_lower, [y_pat])
        if x_col and y_col:
            total = len(df)
            missing = int(df[x_col].isna().sum() | df[y_col].isna().sum())
            return PlanarCoordinateInfo(
                x_column=x_col,
                y_column=y_col,
                detection_method="planar_heuristic",
                count=total,
                missing_count=missing,
            )
    return None


def _find_column(cols_lower: dict[str, str], patterns: list[str]) -> str | None:
    """Find a column matching any of the patterns."""
    for pat in patterns:
        if pat in cols_lower:
            return cols_lower[pat]
    return None


def _validate_coordinates(df: pd.DataFrame, info: CoordinateInfo) -> None:
    """Validate coordinate values as lat/lon."""
    lat_col = info.lat_column
    lon_col = info.lon_column

    if not lat_col or not lon_col:
        return

    total = len(df)
    info.total_count = total

    lat_series = pd.to_numeric(df[lat_col], errors="coerce")
    lon_series = pd.to_numeric(df[lon_col], errors="coerce")

    missing_mask = lat_series.isna() | lon_series.isna()
    info.missing_count = int(missing_mask.sum())

    valid_rows_lat = lat_series[~missing_mask]
    valid_rows_lon = lon_series[~missing_mask]
    if valid_rows_lat.empty:
        info.valid_count = 0
        info.invalid_count = 0
        return

    lat_valid = (valid_rows_lat >= -90) & (valid_rows_lat <= 90)
    lon_valid = (valid_rows_lon >= -180) & (valid_rows_lon <= 180)
    both_valid = lat_valid & lon_valid

    info.valid_count = int(both_valid.sum())
    info.invalid_count = int((~both_valid).sum())


def validate_lat_lon(lat: float, lon: float) -> bool:
    """Check if lat/lon values are valid."""
    return -90 <= lat <= 90 and -180 <= lon <= 180

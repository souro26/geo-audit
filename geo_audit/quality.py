"""Data quality checks: duplicates."""

import pandas as pd


def detect_exact_duplicates(
    df: pd.DataFrame, lat_col: str, lon_col: str
) -> tuple[int, float]:
    """Detect exact duplicate coordinate pairs."""
    valid = df.dropna(subset=[lat_col, lon_col])
    if valid.empty:
        return 0, 0.0

    dup_mask = valid.duplicated(subset=[lat_col, lon_col], keep=False)
    dup_count = int(dup_mask.sum())
    dup_pct = (dup_count / len(valid) * 100) if len(valid) > 0 else 0.0
    return dup_count, dup_pct

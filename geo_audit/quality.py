"""Data quality checks: missingness, duplicates."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class MissingnessThresholds:
    info: float = 5.0
    warning: float = 20.0


def assess_missingness(percentage: float, thresholds: MissingnessThresholds | None = None) -> str:
    """Assess missingness severity."""
    if thresholds is None:
        thresholds = MissingnessThresholds()
    if percentage >= thresholds.warning:
        return "high"
    elif percentage >= thresholds.info:
        return "warning"
    return "info"


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

"""Schema and type inspection."""

from collections import defaultdict
from typing import Any

from geo_audit.models import DatasetInfo


def normalize_column_name(name: str) -> str:
    """Normalize column name for comparison."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def compare_schemas(datasets: list[DatasetInfo]) -> list[dict[str, Any]]:
    """Compare column names and types across datasets."""
    column_map: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for ds in datasets:
        for cp in ds.column_profiles:
            norm = normalize_column_name(cp.name)
            column_map[norm].append((cp.name, cp.dtype, ds.filename))

    observations = []

    for norm_name, entries in column_map.items():
        if len(entries) < 2:
            continue

        dtypes = {e[1] for e in entries}
        if len(dtypes) > 1:
            details = ", ".join(f"{e[0]} ({e[1]}) in {e[2]}" for e in entries)
            observations.append({
                "type": "type_mismatch",
                "normalized_name": norm_name,
                "message": f"Column '{norm_name}' has different types across datasets: {details}",
                "severity": "warning",
                "datasets": [e[2] for e in entries],
            })

        original_names = {e[0] for e in entries}
        if len(original_names) > 1:
            details = ", ".join(f"'{e[0]}' in {e[2]}" for e in entries)
            observations.append({
                "type": "name_variation",
                "normalized_name": norm_name,
                "message": f"Similar column names across datasets: {details}",
                "severity": "info",
                "datasets": [e[2] for e in entries],
            })

    return observations


def find_common_columns(datasets: list[DatasetInfo]) -> dict[str, list[str]]:
    """Find columns that appear in multiple datasets (by normalized name)."""
    column_map: dict[str, list[str]] = defaultdict(list)

    for ds in datasets:
        for cp in ds.column_profiles:
            norm = normalize_column_name(cp.name)
            if ds.filename not in column_map[norm]:
                column_map[norm].append(ds.filename)

    return {k: v for k, v in column_map.items() if len(v) > 1}

"""Spatial analysis: extent, overlap."""

from typing import Any

from geo_audit.models import CrossDatasetOverlap, DatasetInfo


def compute_cross_dataset_overlaps(datasets: list[DatasetInfo]) -> list[CrossDatasetOverlap]:
    """Compute bounding box overlaps between all dataset pairs."""
    overlaps = []
    spatial_datasets = [d for d in datasets if d.bounding_box is not None]

    for i, ds_a in enumerate(spatial_datasets):
        for ds_b in spatial_datasets[i + 1:]:
            box_a = ds_a.bounding_box
            box_b = ds_b.bounding_box

            if box_a is None or box_b is None:
                continue

            overlaps_bool = box_a.overlaps(box_b)

            overlaps.append(CrossDatasetOverlap(
                dataset_a=ds_a.filename,
                dataset_b=ds_b.filename,
                bounding_boxes_overlap=overlaps_bool,
            ))

    return overlaps


def get_spatial_summary(datasets: list[DatasetInfo]) -> dict[str, Any]:
    """Generate spatial coverage summary."""
    spatial = [d for d in datasets if d.bounding_box is not None]
    if not spatial:
        return {"datasets_with_spatial": 0}

    all_lats = []
    all_lons = []
    for ds in spatial:
        bb = ds.bounding_box
        all_lats.extend([bb.min_lat, bb.max_lat])
        all_lons.extend([bb.min_lon, bb.max_lon])

    return {
        "datasets_with_spatial": len(spatial),
        "global_min_lat": min(all_lats),
        "global_max_lat": max(all_lats),
        "global_min_lon": min(all_lons),
        "global_max_lon": max(all_lons),
    }

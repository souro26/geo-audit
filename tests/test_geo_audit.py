"""Tests for geo-audit."""

from pathlib import Path

import pandas as pd
import pytest

from geo_audit.coordinates import (
    detect_coordinate_columns,
    detect_planar_coordinates,
    validate_lat_lon,
)
from geo_audit.discovery import discover_files, get_file_format, get_file_size
from geo_audit.models import (
    BoundingBox,
    ColumnProfile,
    CoordinateInfo,
    DatasetInfo,
    FileFormat,
    PlanarCoordinateInfo,
)
from geo_audit.quality import detect_exact_duplicates
from geo_audit.schema import compare_schemas, normalize_column_name
from geo_audit.spatial import compute_cross_dataset_overlaps


class TestCoordinateDetection:
    def test_valid_lat_lon_detection(self):
        df = pd.DataFrame({
            "latitude": [-23.5, -23.6, -23.7],
            "longitude": [134.1, 134.2, 134.3],
            "value": [1, 2, 3],
        })
        info = detect_coordinate_columns(df)
        assert info.lat_column == "latitude"
        assert info.lon_column == "longitude"
        assert info.detection_method == "explicit_lat_lon"
        assert info.confidence == 0.95

    def test_lat_lon_short_names(self):
        df = pd.DataFrame({
            "lat": [-23.5, -23.6],
            "lon": [134.1, 134.2],
        })
        info = detect_coordinate_columns(df)
        assert info.lat_column == "lat"
        assert info.lon_column == "lon"

    def test_lat_lng_variations(self):
        df = pd.DataFrame({
            "lat": [-23.5],
            "lng": [134.1],
        })
        info = detect_coordinate_columns(df)
        assert info.lat_column == "lat"
        assert info.lon_column == "lng"

    def test_missing_coordinates(self):
        df = pd.DataFrame({
            "latitude": [-23.5, None, -23.7],
            "longitude": [134.1, 134.2, None],
        })
        info = detect_coordinate_columns(df)
        assert info.total_count == 3
        assert info.missing_count == 2
        assert info.missing_percentage > 0

    def test_invalid_coordinates(self):
        df = pd.DataFrame({
            "latitude": [-23.5, -95.0, 100.0],
            "longitude": [134.1, 134.2, 134.3],
        })
        info = detect_coordinate_columns(df)
        assert info.invalid_count == 2
        assert info.invalid_percentage > 0

    def test_no_lat_lon_columns(self):
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })
        info = detect_coordinate_columns(df)
        assert info.lat_column is None
        assert info.lon_column is None
        assert info.detection_method == "none"

    def test_planar_coordinate_detection(self):
        df = pd.DataFrame({
            "easting": [500000, 500100, 500200],
            "northing": [7400000, 7400100, 7400200],
        })
        info = detect_planar_coordinates(df)
        assert info is not None
        assert info.x_column == "easting"
        assert info.y_column == "northing"
        assert info.detection_method == "planar_heuristic"
        assert info.count == 3

    def test_planar_coordinate_missing(self):
        df = pd.DataFrame({
            "easting": [500000, None, 500200],
            "northing": [7400000, 7400100, 7400200],
        })
        info = detect_planar_coordinates(df)
        assert info.missing_count == 1
        assert info.missing_percentage > 0

    def test_validate_lat_lon(self):
        assert validate_lat_lon(0, 0) is True
        assert validate_lat_lon(-90, -180) is True
        assert validate_lat_lon(90, 180) is True
        assert validate_lat_lon(-91, 0) is False
        assert validate_lat_lon(0, 181) is False


class TestDuplicateDetection:
    def test_exact_duplicates(self):
        df = pd.DataFrame({
            "lat": [-23.5, -23.5, -23.6],
            "lon": [134.1, 134.1, 134.2],
        })
        count, pct = detect_exact_duplicates(df, "lat", "lon")
        assert count == 2
        assert pct > 0

    def test_no_duplicates(self):
        df = pd.DataFrame({
            "lat": [-23.5, -23.6, -23.7],
            "lon": [134.1, 134.2, 134.3],
        })
        count, pct = detect_exact_duplicates(df, "lat", "lon")
        assert count == 0
        assert pct == 0.0

    def test_duplicates_with_missing(self):
        df = pd.DataFrame({
            "lat": [-23.5, -23.5, None],
            "lon": [134.1, 134.1, 134.2],
        })
        count, pct = detect_exact_duplicates(df, "lat", "lon")
        assert count == 2
        assert pct == 100.0  # 2 out of 2 valid rows


class TestSchemaComparison:
    def test_normalize_column_name(self):
        assert normalize_column_name("Uranium_Grade") == "uranium_grade"
        assert normalize_column_name("uranium-grade") == "uranium_grade"
        assert normalize_column_name("Uranium Grade") == "uranium_grade"
        assert normalize_column_name("sample_id") == "sample_id"

    def test_type_mismatch_detection(self):
        from geo_audit.models import FileFormat
        cp1 = ColumnProfile(
            name="grade", dtype="float64", missing_count=0, missing_percentage=0, unique_count=5
        )
        cp2 = ColumnProfile(
            name="grade", dtype="object", missing_count=0, missing_percentage=0, unique_count=5
        )
        ds1 = DatasetInfo(
            filename="a.csv", format=FileFormat.CSV, row_count=10, columns=["grade"],
            column_profiles=[cp1], file_size_bytes=100,
        )
        ds2 = DatasetInfo(
            filename="b.csv", format=FileFormat.CSV, row_count=10, columns=["grade"],
            column_profiles=[cp2], file_size_bytes=100,
        )
        obs = compare_schemas([ds1, ds2])
        assert len(obs) == 1
        assert obs[0]["type"] == "type_mismatch"

    def test_name_variation_detection(self):
        from geo_audit.models import FileFormat
        cp1 = ColumnProfile(
            name="sample_id", dtype="str", missing_count=0, missing_percentage=0, unique_count=5
        )
        cp2 = ColumnProfile(
            name="Sample_ID", dtype="str", missing_count=0, missing_percentage=0, unique_count=5
        )
        ds1 = DatasetInfo(
            filename="a.csv", format=FileFormat.CSV, row_count=10, columns=["sample_id"],
            column_profiles=[cp1], file_size_bytes=100,
        )
        ds2 = DatasetInfo(
            filename="b.csv", format=FileFormat.CSV, row_count=10, columns=["Sample_ID"],
            column_profiles=[cp2], file_size_bytes=100,
        )
        obs = compare_schemas([ds1, ds2])
        assert len(obs) == 1
        assert obs[0]["type"] == "name_variation"


class TestBoundingBox:
    def test_overlaps_true(self):
        b1 = BoundingBox(min_lat=-23.5, max_lat=-23.4, min_lon=134.1, max_lon=134.2)
        b2 = BoundingBox(min_lat=-23.45, max_lat=-23.35, min_lon=134.15, max_lon=134.25)
        assert b1.overlaps(b2) is True

    def test_overlaps_false(self):
        b1 = BoundingBox(min_lat=-23.5, max_lat=-23.4, min_lon=134.1, max_lon=134.2)
        b2 = BoundingBox(min_lat=-22.0, max_lat=-21.0, min_lon=135.0, max_lon=136.0)
        assert b1.overlaps(b2) is False

    def test_overlaps_edge(self):
        b1 = BoundingBox(min_lat=0, max_lat=10, min_lon=0, max_lon=10)
        b2 = BoundingBox(min_lat=10, max_lat=20, min_lon=0, max_lon=10)
        assert b1.overlaps(b2) is True  # Touching edges count as overlap


class TestCrossDatasetOverlap:
    def test_compute_overlaps(self):
        from geo_audit.models import BoundingBox, FileFormat
        bb1 = BoundingBox(min_lat=-23.5, max_lat=-23.4, min_lon=134.1, max_lon=134.2)
        ds1 = DatasetInfo(
            filename="a.csv", format=FileFormat.CSV, row_count=10, columns=[],
            column_profiles=[], file_size_bytes=100,
            bounding_box=bb1,
        )
        bb2 = BoundingBox(min_lat=-23.45, max_lat=-23.35, min_lon=134.15, max_lon=134.25)
        ds2 = DatasetInfo(
            filename="b.csv", format=FileFormat.CSV, row_count=10, columns=[],
            column_profiles=[], file_size_bytes=100,
            bounding_box=bb2,
        )
        bb3 = BoundingBox(min_lat=-22.0, max_lat=-21.0, min_lon=135.0, max_lon=136.0)
        ds3 = DatasetInfo(
            filename="c.csv", format=FileFormat.CSV, row_count=10, columns=[],
            column_profiles=[], file_size_bytes=100,
            bounding_box=bb3,
        )
        overlaps = compute_cross_dataset_overlaps([ds1, ds2, ds3])
        assert len(overlaps) == 3
        assert overlaps[0].bounding_boxes_overlap is True
        assert overlaps[1].bounding_boxes_overlap is False
        assert overlaps[2].bounding_boxes_overlap is False


class TestFileDiscovery:
    def test_discover_csv(self, tmp_path):
        f1 = tmp_path / "data.csv"
        f1.write_text("a,b\n1,2")
        f2 = tmp_path / "data.geojson"
        f2.write_text('{"type": "FeatureCollection", "features": []}')
        f3 = tmp_path / "readme.txt"
        f3.write_text("ignore me")

        found = list(discover_files(tmp_path))
        assert len(found) == 2
        formats = [f for _, f in found]
        assert FileFormat.CSV in formats
        assert FileFormat.GEOJSON in formats

    def test_get_file_format(self):
        assert get_file_format(Path("test.csv")) == FileFormat.CSV
        assert get_file_format(Path("test.geojson")) == FileFormat.GEOJSON
        assert get_file_format(Path("test.json")) == FileFormat.GEOJSON
        assert get_file_format(Path("test.txt")) == FileFormat.UNKNOWN

    def test_get_file_size(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a,b\n1,2")
        size = get_file_size(f)
        assert size > 0


class TestModels:
    def test_coordinate_info_percentages(self):
        info = CoordinateInfo(total_count=100, valid_count=90, missing_count=5, invalid_count=5)
        assert info.valid_percentage == 90.0
        assert info.missing_percentage == 5.0
        assert info.invalid_percentage == 5.0

    def test_planar_coordinate_info_percentages(self):
        info = PlanarCoordinateInfo(
            x_column="x", y_column="y", detection_method="test", count=100, missing_count=10
        )
        assert info.missing_percentage == 10.0

    def test_bounding_box_to_dict(self):
        bb = BoundingBox(min_lat=-23.5, max_lat=-23.4, min_lon=134.1, max_lon=134.2)
        d = bb.to_dict()
        assert d["min_lat"] == -23.5
        assert d["max_lat"] == -23.4
        assert d["min_lon"] == 134.1
        assert d["max_lon"] == 134.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

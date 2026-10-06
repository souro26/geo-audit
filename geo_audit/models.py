"""Data models for geo-audit."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DatasetReadiness(str, Enum):
    READY = "ready"
    REVIEW = "review"
    HIGH_RISK = "high_risk"
    ERROR = "error"


class FileFormat(str, Enum):
    CSV = "csv"
    GEOJSON = "geojson"
    UNKNOWN = "unknown"


class GeometryType(str, Enum):
    POINT = "Point"
    LINESTRING = "LineString"
    POLYGON = "Polygon"
    MULTIPOINT = "MultiPoint"
    MULTILINESTRING = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"
    GEOMETRYCOLLECTION = "GeometryCollection"
    UNKNOWN = "unknown"


class FindingCategory(str, Enum):
    COORDINATES = "coordinates"
    DUPLICATES = "duplicates"
    MISSINGNESS = "missingness"
    SCHEMA = "schema"
    CRS = "crs"
    PARSE_ERROR = "parse_error"
    SPATIAL = "spatial"


@dataclass
class Finding:
    severity: Severity
    dataset: str
    category: FindingCategory
    title: str
    details: str
    why_it_matters: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "dataset": self.dataset,
            "category": self.category.value,
            "title": self.title,
            "details": self.details,
            "why_it_matters": self.why_it_matters,
            "recommended_action": self.recommended_action,
        }


@dataclass
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def overlaps(self, other: "BoundingBox") -> bool:
        return not (
            self.max_lon < other.min_lon
            or self.min_lon > other.max_lon
            or self.max_lat < other.min_lat
            or self.min_lat > other.max_lat
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "min_lat": self.min_lat,
            "max_lat": self.max_lat,
            "min_lon": self.min_lon,
            "max_lon": self.max_lon,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "BoundingBox":
        return cls(
            min_lat=data["min_lat"],
            max_lat=data["max_lat"],
            min_lon=data["min_lon"],
            max_lon=data["max_lon"],
        )


@dataclass
class CoordinateInfo:
    lat_column: str | None = None
    lon_column: str | None = None
    detection_method: str = "none"
    confidence: float = 0.0
    valid_count: int = 0
    missing_count: int = 0
    invalid_count: int = 0
    total_count: int = 0

    @property
    def valid_percentage(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.valid_count / self.total_count) * 100

    @property
    def missing_percentage(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.missing_count / self.total_count) * 100

    @property
    def invalid_percentage(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.invalid_count / self.total_count) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "lat_column": self.lat_column,
            "lon_column": self.lon_column,
            "detection_method": self.detection_method,
            "confidence": self.confidence,
            "valid_count": self.valid_count,
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
            "total_count": self.total_count,
            "valid_percentage": round(self.valid_percentage, 2),
            "missing_percentage": round(self.missing_percentage, 2),
            "invalid_percentage": round(self.invalid_percentage, 2),
        }


@dataclass
class PlanarCoordinateInfo:
    """Planar/unknown coordinate columns (x/y, easting/northing) - CRS unknown."""
    x_column: str
    y_column: str
    detection_method: str
    count: int
    missing_count: int

    @property
    def missing_percentage(self) -> float:
        if self.count == 0:
            return 0.0
        return (self.missing_count / self.count) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_column": self.x_column,
            "y_column": self.y_column,
            "detection_method": self.detection_method,
            "count": self.count,
            "missing_count": self.missing_count,
            "missing_percentage": round(self.missing_percentage, 2),
        }


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    missing_count: int
    missing_percentage: float
    unique_count: int
    sample_values: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "missing_count": self.missing_count,
            "missing_percentage": round(self.missing_percentage, 2),
            "unique_count": self.unique_count,
            "sample_values": self.sample_values[:5],
        }


@dataclass
class DatasetInfo:
    filename: str
    format: FileFormat
    row_count: int
    columns: list[str]
    column_profiles: list[ColumnProfile]
    file_size_bytes: int
    coordinate_info: CoordinateInfo | None = None
    planar_coordinate_info: PlanarCoordinateInfo | None = None
    geometry_types: list[GeometryType] = field(default_factory=list)
    crs: str | None = None
    bounding_box: BoundingBox | None = None
    duplicate_count: int = 0
    duplicate_percentage: float = 0.0
    parse_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "format": self.format.value,
            "row_count": self.row_count,
            "columns": self.columns,
            "column_profiles": [cp.to_dict() for cp in self.column_profiles],
            "file_size_bytes": self.file_size_bytes,
            "coordinate_info": self.coordinate_info.to_dict() if self.coordinate_info else None,
            "planar_coordinate_info": (
                self.planar_coordinate_info.to_dict() if self.planar_coordinate_info else None
            ),
            "geometry_types": [gt.value for gt in self.geometry_types],
            "crs": self.crs,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "duplicate_count": self.duplicate_count,
            "duplicate_percentage": round(self.duplicate_percentage, 2),
            "parse_errors": self.parse_errors,
            "warnings": self.warnings,
        }


@dataclass
class CrossDatasetOverlap:
    dataset_a: str
    dataset_b: str
    bounding_boxes_overlap: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_a": self.dataset_a,
            "dataset_b": self.dataset_b,
            "bounding_boxes_overlap": self.bounding_boxes_overlap,
        }


@dataclass
class DatasetReadinessInfo:
    filename: str
    status: DatasetReadiness
    finding_count: int
    highest_severity: Severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "status": self.status.value,
            "finding_count": self.finding_count,
            "highest_severity": self.highest_severity.value,
        }


@dataclass
class AuditReport:
    datasets: list[DatasetInfo]
    cross_dataset_overlaps: list[CrossDatasetOverlap]
    summary: dict[str, Any]
    generated_at: str
    findings: list[Finding] = field(default_factory=list)
    dataset_readiness: list[DatasetReadinessInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasets": [d.to_dict() for d in self.datasets],
            "cross_dataset_overlaps": [o.to_dict() for o in self.cross_dataset_overlaps],
            "summary": self.summary,
            "generated_at": self.generated_at,
            "findings": [f.to_dict() for f in self.findings],
            "dataset_readiness": [d.to_dict() for d in self.dataset_readiness],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


@dataclass
class AuditSummary:
    datasets_scanned: int
    total_records: int
    total_columns: int
    findings_count: int
    by_severity: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasets_scanned": self.datasets_scanned,
            "total_records": self.total_records,
            "total_columns": self.total_columns,
            "findings_count": self.findings_count,
            "by_severity": self.by_severity,
        }

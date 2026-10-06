"""Main CLI entry point."""

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from geo_audit.coordinates import detect_coordinate_columns, detect_planar_coordinates
from geo_audit.discovery import discover_files, get_file_size
from geo_audit.loaders import (
    calculate_bounding_box,
    calculate_bounding_box_from_coords,
    infer_geometry_types,
    load_dataset,
    profile_columns,
)
from geo_audit.models import (
    AuditReport,
    DatasetInfo,
    FileFormat,
)
from geo_audit.quality import detect_exact_duplicates
from geo_audit.reporting import generate_json_report, generate_terminal_report
from geo_audit.spatial import compute_cross_dataset_overlaps

APP_HELP = (
    "Audit heterogeneous geospatial datasets for data-quality "
    "and spatial-consistency problems."
)

app = typer.Typer(
    name="geo-audit",
    help=APP_HELP,
    add_completion=False,
)
console = Console()


@app.command()
def audit(
    input_dir: Path = typer.Argument(..., help="Directory containing geospatial datasets"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (only with --format json)"
    ),
    format: str = typer.Option("terminal", "--format", "-f", help="Output format: terminal, json"),
):
    """Audit geospatial datasets in a directory."""
    if not input_dir.exists() or not input_dir.is_dir():
        console.print(f"[red]Error: {input_dir} is not a valid directory[/red]")
        raise typer.Exit(1)

    if output and format != "json":
        console.print("[red]Error: --output only works with --format json[/red]")
        raise typer.Exit(1)

    datasets = []

    for file_path, file_format in discover_files(input_dir):
        console.print(f"[dim]Processing {file_path.name}...[/dim]")
        ds_info = process_dataset(file_path, file_format)
        datasets.append(ds_info)

    if not datasets:
        console.print("[yellow]No supported datasets found[/yellow]")
        raise typer.Exit(0)

    overlaps = compute_cross_dataset_overlaps(datasets)
    summary = build_summary(datasets, overlaps)

    report = AuditReport(
        datasets=datasets,
        cross_dataset_overlaps=overlaps,
        summary=summary,
        generated_at=datetime.now().isoformat(),
    )

    if format == "json":
        json_output = generate_json_report(report)
        if output:
            output.write_text(json_output)
            console.print(f"[green]Report written to {output}[/green]")
        else:
            console.print(json_output)
    else:
        generate_terminal_report(report)


def process_dataset(file_path: Path, file_format: FileFormat) -> DatasetInfo:
    """Process a single dataset and return DatasetInfo."""
    file_size = get_file_size(file_path)
    data, parse_errors = load_dataset(file_path, file_format)

    if data is None or (hasattr(data, 'empty') and data.empty):
        return DatasetInfo(
            filename=file_path.name,
            format=file_format,
            row_count=0,
            columns=[],
            column_profiles=[],
            file_size_bytes=file_size,
            parse_errors=parse_errors,
        )

    if file_format == FileFormat.CSV:
        columns = list(data.columns)
        column_profiles = profile_columns(data)
        row_count = len(data)

        coord_info = detect_coordinate_columns(data)
        planar_info = detect_planar_coordinates(data)

        duplicate_count = 0
        duplicate_pct = 0.0
        if coord_info.lat_column and coord_info.lon_column:
            duplicate_count, duplicate_pct = detect_exact_duplicates(
                data, coord_info.lat_column, coord_info.lon_column
            )

        bounding_box = None
        if coord_info.lat_column and coord_info.lon_column:
            bounding_box = calculate_bounding_box_from_coords(
                data, coord_info.lat_column, coord_info.lon_column
            )

        warnings = []
        if coord_info.lat_column and coord_info.lon_column:
            if coord_info.missing_percentage > 5:
                warnings.append(f"{coord_info.missing_percentage:.1f}% missing coordinates")
            if coord_info.invalid_percentage > 0:
                warnings.append(f"{coord_info.invalid_percentage:.1f}% invalid coordinates")
            if duplicate_pct > 1:
                warnings.append(f"{duplicate_pct:.1f}% exact duplicate locations")
        if planar_info:
            if planar_info.missing_percentage > 5:
                msg = f"Planar coordinates ({planar_info.x_column}/{planar_info.y_column}): "
                msg += f"{planar_info.missing_percentage:.1f}% missing"
                warnings.append(msg)

        return DatasetInfo(
            filename=file_path.name,
            format=file_format,
            row_count=row_count,
            columns=columns,
            column_profiles=column_profiles,
            file_size_bytes=file_size,
            coordinate_info=coord_info,
            planar_coordinate_info=planar_info,
            bounding_box=bounding_box,
            duplicate_count=duplicate_count,
            duplicate_percentage=duplicate_pct,
            parse_errors=parse_errors,
            warnings=warnings,
        )

    else:
        columns = [c for c in data.columns if c != 'geometry']
        non_geom = data.drop(columns=['geometry']) if 'geometry' in data.columns else data
        column_profiles = profile_columns(non_geom)
        row_count = len(data)

        geometry_types = infer_geometry_types(data)
        crs = str(data.crs) if data.crs else None
        bounding_box = calculate_bounding_box(data)

        warnings = []
        if crs is None:
            warnings.append("No CRS declared in file (GeoJSON spec assumes WGS84)")

        return DatasetInfo(
            filename=file_path.name,
            format=file_format,
            row_count=row_count,
            columns=columns,
            column_profiles=column_profiles,
            file_size_bytes=file_size,
            geometry_types=geometry_types,
            crs=crs,
            bounding_box=bounding_box,
            parse_errors=parse_errors,
            warnings=warnings,
        )


def _has_coords(d: DatasetInfo) -> bool:
    return d.coordinate_info is not None and d.coordinate_info.total_count > 0


def build_summary(datasets: list[DatasetInfo], overlaps: list) -> dict:
    """Build summary statistics."""
    total_records = sum(d.row_count for d in datasets)
    total_columns = sum(len(d.columns) for d in datasets)
    datasets_with_coords = sum(1 for d in datasets if _has_coords(d))
    datasets_with_spatial = sum(1 for d in datasets if d.bounding_box is not None)

    warnings = 0
    errors = 0
    for d in datasets:
        warnings += len(d.warnings)
        errors += len(d.parse_errors)

    return {
        "datasets_scanned": len(datasets),
        "total_records": total_records,
        "total_columns": total_columns,
        "warnings": warnings,
        "errors": errors,
        "datasets_with_coords": datasets_with_coords,
        "datasets_with_spatial": datasets_with_spatial,
    }


if __name__ == "__main__":
    app()

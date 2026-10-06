"""Report generation: terminal, JSON."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from geo_audit.models import AuditReport
from geo_audit.schema import compare_schemas

console = Console()


def generate_terminal_report(report: AuditReport) -> None:
    """Print human-readable report to terminal."""
    _print_header(report)
    _print_summary(report)
    _print_dataset_inventory(report)
    _print_coordinate_quality(report)
    _print_missingness(report)
    _print_schema_observations(report)
    _print_crs_info(report)
    _print_spatial_coverage(report)
    _print_cross_dataset_overlap(report)
    _print_warnings(report)


def _print_header(report: AuditReport) -> None:
    console.print("\n[bold cyan]=== geo-audit Report ===[/bold cyan]")
    console.print(f"Generated: {report.generated_at}\n")


def _print_summary(report: AuditReport) -> None:
    summary = report.summary
    table = Table(title="Executive Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Datasets scanned", str(summary.get("datasets_scanned", 0)))
    table.add_row("Total records", f"{summary.get('total_records', 0):,}")
    table.add_row("Total columns", str(summary.get("total_columns", 0)))
    table.add_row("Warnings", str(summary.get("warnings", 0)))
    table.add_row("Errors", str(summary.get("errors", 0)))
    table.add_row(
            "Datasets with geographic coordinates", str(summary.get("datasets_with_coords", 0))
        )
    table.add_row("Datasets with spatial extent", str(summary.get("datasets_with_spatial", 0)))

    console.print(table)
    console.print()


def _print_dataset_inventory(report: AuditReport) -> None:
    table = Table(title="Dataset Inventory")
    table.add_column("File", style="cyan")
    table.add_column("Format", style="green")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Size", justify="right")

    for ds in report.datasets:
        size_kb = ds.file_size_bytes / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        table.add_row(
            ds.filename,
            ds.format.value.upper(),
            f"{ds.row_count:,}",
            str(len(ds.columns)),
            size_str,
        )

    console.print(table)
    console.print()


def _print_coordinate_quality(report: AuditReport) -> None:
    table = Table(title="Geographic Coordinate Quality (explicit lat/lon)")
    table.add_column("Dataset", style="cyan")
    table.add_column("Lat Column", style="yellow")
    table.add_column("Lon Column", style="yellow")
    table.add_column("Method", style="dim")
    table.add_column("Confidence", justify="right")
    table.add_column("Valid %", justify="right", style="green")
    table.add_column("Missing %", justify="right", style="yellow")
    table.add_column("Invalid %", justify="right", style="red")

    for ds in report.datasets:
        if ds.coordinate_info and ds.coordinate_info.total_count > 0:
            ci = ds.coordinate_info
            table.add_row(
                ds.filename,
                ci.lat_column or "—",
                ci.lon_column or "—",
                ci.detection_method,
                f"{ci.confidence:.0%}",
                f"{ci.valid_percentage:.1f}%",
                f"{ci.missing_percentage:.1f}%",
                f"{ci.invalid_percentage:.1f}%",
            )
        else:
            table.add_row(ds.filename, "—", "—", "none", "0%", "—", "—", "—")

    console.print(table)

    # Planar coordinates
    planar_any = any(ds.planar_coordinate_info for ds in report.datasets)
    if planar_any:
        console.print()
        table2 = Table(title="Planar/Unknown Coordinates (x/y, easting/northing - CRS unknown)")
        table2.add_column("Dataset", style="cyan")
        table2.add_column("X Column", style="yellow")
        table2.add_column("Y Column", style="yellow")
        table2.add_column("Method", style="dim")
        table2.add_column("Count", justify="right")
        table2.add_column("Missing %", justify="right", style="yellow")

        for ds in report.datasets:
            if ds.planar_coordinate_info:
                pi = ds.planar_coordinate_info
                table2.add_row(
                    ds.filename,
                    pi.x_column,
                    pi.y_column,
                    pi.detection_method,
                    str(pi.count),
                    f"{pi.missing_percentage:.1f}%",
                )
            else:
                table2.add_row(ds.filename, "—", "—", "none", "0", "—")

        console.print(table2)
    console.print()


def _print_missingness(report: AuditReport) -> None:
    table = Table(title="Column Missingness (columns with >5% missing)")
    table.add_column("Dataset", style="cyan")
    table.add_column("Column", style="yellow")
    table.add_column("Type", style="dim")
    table.add_column("Missing %", justify="right")
    table.add_column("Severity", justify="center")

    any_missing = False
    for ds in report.datasets:
        for cp in ds.column_profiles:
            if cp.missing_percentage >= 5.0:
                any_missing = True
                if cp.missing_percentage >= 20:
                    sev = "HIGH"
                elif cp.missing_percentage >= 5:
                    sev = "WARN"
                else:
                    sev = "INFO"
                sev_style = "red" if sev == "HIGH" else "yellow" if sev == "WARN" else "green"
                table.add_row(
                    ds.filename,
                    cp.name,
                    cp.dtype,
                    f"{cp.missing_percentage:.1f}%",
                    f"[{sev_style}]{sev}[/{sev_style}]",
                )

    if not any_missing:
        console.print("[green]No columns with significant missingness (>5%)[/green]")
    else:
        console.print(table)
    console.print()


def _print_schema_observations(report: AuditReport) -> None:
    observations = compare_schemas(report.datasets)
    if not observations:
        console.print("[green]No schema inconsistencies detected[/green]")
        console.print()
        return

    table = Table(title="Schema Observations")
    table.add_column("Type", style="cyan")
    table.add_column("Normalized Name", style="yellow")
    table.add_column("Message")
    table.add_column("Severity", justify="center")

    for obs in observations:
        sev_style = "red" if obs["severity"] == "warning" else "green"
        table.add_row(
            obs["type"].replace("_", " ").title(),
            obs["normalized_name"],
            obs["message"],
            f"[{sev_style}]{obs['severity'].upper()}[/{sev_style}]",
        )

    console.print(table)
    console.print()


def _print_crs_info(report: AuditReport) -> None:
    table = Table(title="CRS / Spatial Reference")
    table.add_column("Dataset", style="cyan")
    table.add_column("CRS", style="yellow")
    table.add_column("Geometry Types", style="dim")

    for ds in report.datasets:
        crs = ds.crs or "unknown / not declared"
        geom_types = ", ".join(gt.value for gt in ds.geometry_types) if ds.geometry_types else "—"
        table.add_row(ds.filename, crs, geom_types)

    console.print(table)
    console.print()


def _print_spatial_coverage(report: AuditReport) -> None:
    table = Table(title="Spatial Coverage (Bounding Boxes)")
    table.add_column("Dataset", style="cyan")
    table.add_column("Min Lat", justify="right")
    table.add_column("Max Lat", justify="right")
    table.add_column("Min Lon", justify="right")
    table.add_column("Max Lon", justify="right")

    for ds in report.datasets:
        if ds.bounding_box:
            bb = ds.bounding_box
            table.add_row(
                ds.filename,
                f"{bb.min_lat:.6f}",
                f"{bb.max_lat:.6f}",
                f"{bb.min_lon:.6f}",
                f"{bb.max_lon:.6f}",
            )
        else:
            table.add_row(ds.filename, "—", "—", "—", "—")

    console.print(table)
    console.print()


def _print_cross_dataset_overlap(report: AuditReport) -> None:
    if not report.cross_dataset_overlaps:
        console.print("[dim]No spatial datasets to compare[/dim]")
        console.print()
        return

    table = Table(title="Cross-Dataset Spatial Overlap (Bounding Box)")
    table.add_column("Dataset A", style="cyan")
    table.add_column("Dataset B", style="cyan")
    table.add_column("Boxes Overlap", justify="center")

    for ov in report.cross_dataset_overlaps:
        overlap_str = "[green]YES[/green]" if ov.bounding_boxes_overlap else "[red]NO[/red]"
        table.add_row(ov.dataset_a, ov.dataset_b, overlap_str)

    console.print(table)
    console.print()


def _print_warnings(report: AuditReport) -> None:
    warnings = []
    errors = []

    for ds in report.datasets:
        for warn in ds.warnings:
            warnings.append(f"{ds.filename}: {warn}")
        for err in ds.parse_errors:
            errors.append(f"{ds.filename}: {err}")

    # Add coordinate quality warnings (only if not already in ds.warnings)
    for ds in report.datasets:
        if ds.coordinate_info:
            ci = ds.coordinate_info
            has_missing_warn = any("missing coordinates" in w for w in ds.warnings)
            if ci.missing_percentage > 5 and not has_missing_warn:
                warnings.append(
                    f"{ds.filename}: {ci.missing_percentage:.1f}% records have missing coordinates"
                )
            has_invalid_warn = any("invalid coordinates" in w for w in ds.warnings)
            if ci.invalid_percentage > 0 and not has_invalid_warn:
                warnings.append(
                    f"{ds.filename}: {ci.invalid_percentage:.1f}% records have invalid coordinates"
                )
            if ci.valid_percentage < 95 and ci.total_count > 0:
                warnings.append(
                    f"{ds.filename}: Only {ci.valid_percentage:.1f}% records have valid coordinates"
                )
            if ds.duplicate_percentage > 1:
                msg = f"{ds.filename}: {ds.duplicate_count} exact duplicate locations "
                msg += f"({ds.duplicate_percentage:.1f}%)"
                warnings.append(msg)

        for cp in ds.column_profiles:
            if cp.missing_percentage >= 20:
                msg = f"{ds.filename}: Column '{cp.name}' has "
                msg += f"{cp.missing_percentage:.1f}% missing values"
                warnings.append(msg)

    # Cross-dataset: report non-overlap as info, not warning
    # (non-overlapping datasets may be perfectly valid)
    # No automatic warning for non-overlapping bounding boxes

    if errors:
        console.print(Panel("\n".join(errors), title="[red]Errors[/red]", border_style="red"))
        console.print()

    if warnings:
        panel_content = "\n".join(warnings)
        panel = Panel(panel_content, title="[yellow]Warnings[/yellow]", border_style="yellow")
        console.print(panel)
    else:
        console.print("[green]No warnings[/green]")
    console.print()


def generate_json_report(report: AuditReport) -> str:
    """Generate JSON report."""
    return report.to_json()


def write_report(report: AuditReport, output_path: str) -> None:
    """Write JSON report to file."""
    content = generate_json_report(report)
    with open(output_path, "w") as f:
        f.write(content)

"""Report generation: terminal, JSON."""

from rich.box import ASCII
from rich.console import Console
from rich.table import Table

from geo_audit.models import AuditReport, DatasetReadiness, Severity
from geo_audit.schema import compare_schemas

console = Console(force_terminal=True, color_system="standard", legacy_windows=False)


SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "green",
    Severity.INFO: "blue",
}

READINESS_STYLE = {
    DatasetReadiness.READY: "green",
    DatasetReadiness.REVIEW: "yellow",
    DatasetReadiness.HIGH_RISK: "red",
    DatasetReadiness.ERROR: "bold red",
}

READINESS_LABEL = {
    DatasetReadiness.READY: "READY",
    DatasetReadiness.REVIEW: "REVIEW",
    DatasetReadiness.HIGH_RISK: "HIGH RISK",
    DatasetReadiness.ERROR: "ERROR",
}


def generate_terminal_report(report: AuditReport) -> None:
    """Print human-readable triage-oriented report to terminal."""
    _print_triage_header(report)
    _print_overall_assessment(report)
    _print_top_priorities(report)
    _print_dataset_readiness(report)
    console.print()
    _print_detailed_evidence(report)
    _print_technical_notes(report)


def _print_triage_header(report: AuditReport) -> None:
    """Print the top-level triage summary."""
    summary = report.summary
    findings = report.findings

    # Count by severity
    sev_counts = {s.value: 0 for s in Severity}
    for f in findings:
        sev_counts[f.severity.value] += 1

    # Overall status
    if any(f.severity == Severity.CRITICAL for f in findings):
        status = "ERROR"
        status_style = "bold red"
    elif any(f.severity == Severity.HIGH for f in findings):
        status = "NEEDS REVIEW"
        status_style = "bold red"
    elif any(f.severity == Severity.MEDIUM for f in findings):
        status = "NEEDS REVIEW"
        status_style = "bold yellow"
    elif findings:
        status = "OK WITH NOTES"
        status_style = "green"
    else:
        status = "READY"
        status_style = "bold green"

    console.print("\n[bold cyan]GEO-AUDIT[/bold cyan]")
    console.print("[bold cyan]DATA READINESS REPORT[/bold cyan]\n")

    console.print(f"STATUS: [{status_style}]{status}[/{status_style}]\n")

    console.print(
        f"{summary.get('datasets_scanned', 0)} datasets scanned · "
        f"{summary.get('total_records', 0):,} records · "
        f"{summary.get('total_columns', 0)} columns\n"
    )

    total_findings = len(findings)
    high = sev_counts["high"]
    medium = sev_counts["medium"]
    low = sev_counts["low"]
    critical = sev_counts["critical"]

    console.print(
        f"{total_findings} findings require attention\n"
        f"{critical} critical · {high} high · {medium} medium · {low} low\n"
    )


def _print_overall_assessment(report: AuditReport) -> None:
    """Print overall assessment summary."""
    readiness = report.dataset_readiness

    # Count datasets by readiness
    ready_count = sum(1 for r in readiness if r.status == DatasetReadiness.READY)
    review_count = sum(1 for r in readiness if r.status == DatasetReadiness.REVIEW)
    high_risk_count = sum(1 for r in readiness if r.status == DatasetReadiness.HIGH_RISK)
    error_count = sum(1 for r in readiness if r.status == DatasetReadiness.ERROR)

    # Overall assessment
    if error_count > 0:
        assessment = "NOT READY FOR DOWNSTREAM SPATIAL ML"
    elif high_risk_count > 0:
        assessment = "NOT READY FOR DOWNSTREAM SPATIAL ML"
    elif review_count > 0:
        assessment = "REVIEW RECOMMENDED BEFORE DOWNSTREAM USE"
    else:
        assessment = "NO BLOCKING ISSUES DETECTED"

    console.print("OVERALL ASSESSMENT")
    console.print("-" * 60)
    console.print(f"\n{assessment}\n")

    if ready_count:
        console.print(f"{ready_count} dataset(s) have no flagged issues.")
    if review_count:
        console.print(f"{review_count} dataset(s) require review.")
    if high_risk_count:
        console.print(f"{high_risk_count} dataset(s) are HIGH RISK.")
    if error_count:
        console.print(f"{error_count} dataset(s) have ERRORS.")

    console.print()

    # Dataset breakdown by status
    if high_risk_count:
        console.print("[red]HIGH RISK:[/red]")
        for r in report.dataset_readiness:
            if r.status == DatasetReadiness.HIGH_RISK:
                console.print(f"  {r.filename}")
        console.print()

    if review_count:
        console.print("[yellow]REVIEW:[/yellow]")
        for r in report.dataset_readiness:
            if r.status == DatasetReadiness.REVIEW:
                console.print(f"  {r.filename}")
        console.print()

    if ready_count:
        console.print("[green]READY:[/green]")
        for r in report.dataset_readiness:
            if r.status == DatasetReadiness.READY:
                console.print(f"  {r.filename}")
        console.print()


def _print_top_priorities(report: AuditReport) -> None:
    """Print the top priority findings with why-it-matters and actions."""
    findings = report.findings
    if not findings:
        console.print("[green]No actionable findings.[/green]\n")
        return

    console.print("TOP PRIORITIES")
    console.print("-" * 60)

    for i, f in enumerate(findings, 1):
        sev_style = SEVERITY_STYLE.get(f.severity, "white")
        sev_label = f.severity.value.upper()

        console.print(f"\n[{sev_style}]{i}. {sev_label}[/{sev_style}]   {f.dataset}")
        console.print(f"   {f.title}")
        console.print(f"   {f.details}")
        console.print(f"   [dim]Why it matters:[/dim] {f.why_it_matters}")
        console.print(f"   [dim]Recommended action:[/dim] {f.recommended_action}")

    console.print("\n" + "-" * 60 + "\n")


def _print_dataset_readiness(report: AuditReport) -> None:
    """Print dataset readiness table."""
    console.print("DATASET READINESS")
    console.print("-" * 60)

    table = Table(box=ASCII, show_header=True, header_style="bold")
    table.add_column("Dataset", style="cyan", min_width=25)
    table.add_column("Status", justify="center", min_width=12)
    table.add_column("Findings", justify="right", min_width=8)
    table.add_column("Highest Severity", justify="center", min_width=14)

    for r in report.dataset_readiness:
        style = READINESS_STYLE.get(r.status, "white")
        label = READINESS_LABEL.get(r.status, r.status.value.upper())
        sev_style = SEVERITY_STYLE.get(r.highest_severity, "white")
        sev_label = r.highest_severity.value.upper()

        table.add_row(
            r.filename,
            f"[{style}]{label}[/{style}]",
            str(r.finding_count),
            f"[{sev_style}]{sev_label}[/{sev_style}]",
        )

    console.print(table)
    console.print()


def _print_detailed_evidence(report: AuditReport) -> None:
    """Print detailed technical evidence tables."""
    _print_dataset_inventory(report)
    _print_coordinate_quality(report)
    _print_missingness(report)
    _print_schema_observations(report)
    _print_crs_info(report)
    _print_spatial_coverage(report)
    _print_potentially_related(report)


def _print_dataset_inventory(report: AuditReport) -> None:
    table = Table(box=ASCII, title="Dataset Inventory")
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
    table = Table(box=ASCII, title="Geographic Coordinate Quality (explicit lat/lon)")
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
        title = "Planar/Unknown Coordinates (x/y, easting/northing - CRS unknown)"
        table2 = Table(box=ASCII, title=title)
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
    table = Table(box=ASCII, title="Column Missingness (columns with >5% missing)")
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

    table = Table(box=ASCII, title="Schema Observations")
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
    table = Table(box=ASCII, title="CRS / Spatial Reference")
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
    table = Table(box=ASCII, title="Spatial Coverage (Bounding Boxes)")
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


def _print_potentially_related(report: AuditReport) -> None:
    """Print potentially related datasets based on spatial overlap and schema."""
    if not report.cross_dataset_overlaps:
        console.print("[dim]No spatial datasets to compare[/dim]")
        console.print()
        return

    # Build a map of spatial overlaps
    overlap_map: dict[tuple[str, str], bool] = {}
    for ov in report.cross_dataset_overlaps:
        overlap_map[(ov.dataset_a, ov.dataset_b)] = ov.bounding_boxes_overlap
        overlap_map[(ov.dataset_b, ov.dataset_a)] = ov.bounding_boxes_overlap

    # Find datasets with geographic coordinates
    spatial_datasets = [
        ds for ds in report.datasets
        if ds.coordinate_info and ds.coordinate_info.total_count > 0
    ]

    if len(spatial_datasets) < 2:
        console.print("[dim]Need at least 2 datasets with geographic coordinates "
                      "for comparison[/dim]")
        console.print()
        return

    console.print("POTENTIALLY RELATED DATASETS")
    console.print("-" * 60)
    console.print(
        "[dim]Datasets with overlapping geographic bounding boxes may warrant "
        "joint inspection or spatial alignment. Overlap is a coarse signal, "
        "not proof of semantic compatibility.[/dim]\n"
    )

    title = "Spatial Overlap & Potential Coordinate Correspondences"
    table = Table(box=ASCII, title=title)
    table.add_column("Dataset A", style="cyan")
    table.add_column("Dataset B", style="cyan")
    table.add_column("Boxes Overlap", justify="center")
    table.add_column("Potential Coordinate Matches", style="dim")

    # Get schema observations for coordinate field matching
    schema_obs = compare_schemas(report.datasets)
    coord_matches: dict[tuple[str, str], list[str]] = {}

    for obs in schema_obs:
        if obs["type"] == "name_variation":
            norm = obs["normalized_name"]
            # Check if this is a coordinate-related field
            coord_terms = [
                "lat", "lon", "lng", "longitude", "latitude",
                "x", "y", "easting", "northing"
            ]
            if any(term in norm for term in coord_terms):
                datasets = obs["datasets"]
                if len(datasets) == 2:
                    key = tuple(sorted(datasets))
                    # Extract field names from the message
                    msg = obs["message"]
                    parts = msg.split("'")
                    if len(parts) >= 4:
                        field1 = parts[1]
                        field2 = parts[3]
                        coord_matches.setdefault(key, []).append(
                            f"{datasets[0]}:{field1} ↔ {datasets[1]}:{field2}"
                        )

    for i, ds_a in enumerate(spatial_datasets):
        for ds_b in spatial_datasets[i + 1:]:
            key = tuple(sorted([ds_a.filename, ds_b.filename]))
            overlap = overlap_map.get(key, False)
            overlap_str = "[green]YES[/green]" if overlap else "[red]NO[/red]"

            matches = coord_matches.get(key, [])
            matches_str = "; ".join(matches) if matches else "—"

            table.add_row(ds_a.filename, ds_b.filename, overlap_str, matches_str)

    console.print(table)
    console.print()


def _print_technical_notes(report: AuditReport) -> None:
    console.print("TECHNICAL NOTES")
    console.print("-" * 60)
    console.print(
        "• Bounding-box overlap is a coarse spatial signal; it does not imply "
        "semantic compatibility or that datasets can be directly joined.\n"
        "• Planar coordinates (x/y, easting/northing) have unknown CRS unless "
        "explicitly declared.\n"
        "• GeoJSON CRS follows the GeoJSON specification (WGS84 if absent).\n"
        "• Findings are static audit signals, not proof of downstream model "
        "failure.\n"
        "• No automatic CRS inference, coordinate transformation, or near-duplicate "
        "detection is performed.\n"
    )


def generate_json_report(report: AuditReport) -> str:
    """Generate JSON report with structured findings."""
    return report.to_json()


def write_report(report: AuditReport, output_path: str) -> None:
    """Write JSON report to file."""
    content = generate_json_report(report)
    with open(output_path, "w") as f:
        f.write(content)

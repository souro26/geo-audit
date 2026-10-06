"""Findings engine: generates structured findings from audit results."""

from geo_audit.models import (
    AuditSummary,
    DatasetInfo,
    DatasetReadiness,
    DatasetReadinessInfo,
    Finding,
    FindingCategory,
    Severity,
)

# Severity thresholds - single source of truth
COORD_MISSING_HIGH = 20.0
COORD_MISSING_MEDIUM = 5.0
COORD_INVALID_HIGH = 20.0
COORD_INVALID_MEDIUM = 5.0
DUPLICATE_HIGH = 20.0
DUPLICATE_MEDIUM = 5.0
MISSINGNESS_HIGH = 20.0
MISSINGNESS_MEDIUM = 5.0
PLANAR_MISSING_MEDIUM = 5.0

# Missingness aggregation thresholds
MISSINGNESS_AGGREGATE_MIN_COLUMNS = 3


def generate_findings(datasets: list[DatasetInfo]) -> list[Finding]:
    """Generate deduplicated, prioritized findings from datasets."""
    findings = []

    for ds in datasets:
        findings.extend(_findings_for_dataset(ds))

    # Sort by severity (critical first) then by dataset name
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    findings.sort(key=lambda f: (severity_order.get(f.severity, 5), f.dataset))
    return findings


def _findings_for_dataset(ds: DatasetInfo) -> list[Finding]:
    """Generate findings for a single dataset."""
    findings = []

    # Parse errors -> CRITICAL
    if ds.parse_errors:
        for err in ds.parse_errors:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                dataset=ds.filename,
                category=FindingCategory.PARSE_ERROR,
                title="Dataset could not be parsed",
                details=f"Parse error: {err}",
                why_it_matters="The dataset cannot be loaded for any downstream processing.",
                recommended_action="Fix the file format or encoding issue before proceeding."
            ))

    # Coordinate quality findings
    if ds.coordinate_info and ds.coordinate_info.total_count > 0:
        ci = ds.coordinate_info
        _add_coordinate_findings(findings, ds, ci)

    # Planar coordinate findings
    if ds.planar_coordinate_info:
        pi = ds.planar_coordinate_info
        _add_planar_findings(findings, ds, pi)

    # Duplicate findings
    if ds.duplicate_count > 0:
        _add_duplicate_findings(findings, ds)

    # Column missingness findings (aggregated)
    _add_missingness_findings(findings, ds)

    return findings


def _add_coordinate_findings(findings: list[Finding], ds: DatasetInfo, ci) -> None:
    """Add coordinate quality findings, deduplicating missing+invalid."""
    missing_pct = ci.missing_percentage
    invalid_pct = ci.invalid_percentage
    unusable_pct = missing_pct + invalid_pct

    if unusable_pct > 0:
        if unusable_pct > COORD_MISSING_HIGH or invalid_pct > COORD_INVALID_HIGH:
            severity = Severity.HIGH
        elif unusable_pct > COORD_MISSING_MEDIUM or invalid_pct > COORD_INVALID_MEDIUM:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        details_parts = []
        if missing_pct > 0:
            details_parts.append(f"{missing_pct:.1f}% missing")
        if invalid_pct > 0:
            details_parts.append(f"{invalid_pct:.1f}% invalid")

        findings.append(Finding(
            severity=severity,
            dataset=ds.filename,
            category=FindingCategory.COORDINATES,
            title="Unusable geographic coordinates",
            details=(
                f"{unusable_pct:.1f}% of records have unusable coordinates "
                f"({', '.join(details_parts)})."
            ),
            why_it_matters=(
                "Records with missing or invalid latitude/longitude cannot be used in "
                "spatial joins, mapping, spatial aggregation, or downstream geospatial ML."
            ),
            recommended_action=(
                "Inspect and correct or remove the affected records before "
                "downstream spatial processing."
            )
        ))

    # Valid percentage check (only if not already captured above)
    if ci.valid_percentage < 95 and ci.total_count > 0 and unusable_pct <= COORD_MISSING_MEDIUM:
        severity = Severity.LOW
        findings.append(Finding(
            severity=severity,
            dataset=ds.filename,
            category=FindingCategory.COORDINATES,
            title="Below-threshold coordinate validity",
            details=f"Only {ci.valid_percentage:.1f}% of records have valid coordinates.",
            why_it_matters=(
                "A small fraction of records have coordinate issues that may affect "
                "spatial analysis quality."
            ),
            recommended_action="Review the affected records if high precision is required."
        ))


def _add_planar_findings(findings: list[Finding], ds: DatasetInfo, pi) -> None:
    """Add planar coordinate findings."""
    if pi.missing_percentage > PLANAR_MISSING_MEDIUM:
        findings.append(Finding(
            severity=Severity.MEDIUM,
            dataset=ds.filename,
            category=FindingCategory.COORDINATES,
            title="Missing planar coordinates",
            details=(
                f"{pi.missing_percentage:.1f}% of {pi.x_column}/{pi.y_column} values "
                "are missing. CRS is unknown for these coordinates."
            ),
            why_it_matters=(
                "Planar coordinates with unknown CRS cannot be reliably transformed to "
                "geographic coordinates or combined with other spatial datasets."
            ),
            recommended_action=(
                "Resolve missing coordinate values and determine the CRS before "
                "spatial analysis."
            )
        ))
    elif pi.missing_percentage > 0:
        findings.append(Finding(
            severity=Severity.LOW,
            dataset=ds.filename,
            category=FindingCategory.COORDINATES,
            title="Some missing planar coordinates",
            details=(
                f"{pi.missing_percentage:.1f}% of {pi.x_column}/{pi.y_column} values "
                "are missing."
            ),
            why_it_matters=(
                "Missing planar coordinates reduce the usable record count for this "
                "dataset."
            ),
            recommended_action=(
                "Consider filling or removing records with missing coordinates."
            )
        ))


def _add_duplicate_findings(findings: list[Finding], ds: DatasetInfo) -> None:
    """Add duplicate location findings."""
    if ds.duplicate_percentage > DUPLICATE_HIGH:
        severity = Severity.HIGH
    elif ds.duplicate_percentage > DUPLICATE_MEDIUM:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    findings.append(Finding(
        severity=severity,
        dataset=ds.filename,
        category=FindingCategory.DUPLICATES,
        title="Exact duplicate geographic locations",
        details=(
            f"{ds.duplicate_count} records ({ds.duplicate_percentage:.1f}%) share "
            "identical latitude/longitude coordinates."
        ),
        why_it_matters=(
            "Duplicate locations may indicate duplicate observations, data entry "
            "errors, or legitimate repeated measurements at the same site."
        ),
        recommended_action=(
            "Determine whether these are duplicate observations or legitimate "
            "repeated measurements. Deduplicate if appropriate."
        )
    ))


def _add_missingness_findings(findings: list[Finding], ds: DatasetInfo) -> None:
    """Add column missingness findings, aggregating moderate missingness.

    Coordinate columns (lat/lon, planar x/y) are excluded here — their
    missingness is already surfaced by the coordinate quality findings.
    """
    # Build the set of columns already covered by a coordinate finding
    coord_cols: set[str] = set()
    if ds.coordinate_info:
        ci = ds.coordinate_info
        if ci.lat_column:
            coord_cols.add(ci.lat_column.lower())
        if ci.lon_column:
            coord_cols.add(ci.lon_column.lower())
    if ds.planar_coordinate_info:
        pi = ds.planar_coordinate_info
        if pi.x_column:
            coord_cols.add(pi.x_column.lower())
        if pi.y_column:
            coord_cols.add(pi.y_column.lower())

    high_missing = []
    medium_missing = []

    for cp in ds.column_profiles:
        if cp.name.lower() in coord_cols:
            continue  # already reported in coordinate finding
        if cp.missing_percentage >= MISSINGNESS_HIGH:
            high_missing.append(cp)
        elif cp.missing_percentage >= MISSINGNESS_MEDIUM:
            medium_missing.append(cp)

    # High missingness: individual findings
    for cp in high_missing:
        findings.append(Finding(
            severity=Severity.HIGH,
            dataset=ds.filename,
            category=FindingCategory.MISSINGNESS,
            title=f"High missingness in column '{cp.name}'",
            details=f"Column '{cp.name}' has {cp.missing_percentage:.1f}% missing values.",
            why_it_matters=(
                "High missingness in important columns can bias analysis and reduce "
                "statistical power."
            ),
            recommended_action=(
                "Assess whether the column is critical for downstream use. Consider "
                "imputation, removal, or accepting the reduced sample size."
            )
        ))

    # Medium missingness: aggregate if many columns, otherwise individual
    if len(medium_missing) >= MISSINGNESS_AGGREGATE_MIN_COLUMNS:
        # Aggregate finding
        top_cols = sorted(medium_missing, key=lambda c: c.missing_percentage, reverse=True)[:5]
        details = (
            f"{len(medium_missing)} columns contain 5-20% missing values.\n"
            "Most affected:\n"
            + "\n".join(f"  {c.name} {c.missing_percentage:.1f}%" for c in top_cols)
        )
        findings.append(Finding(
            severity=Severity.MEDIUM,
            dataset=ds.filename,
            category=FindingCategory.MISSINGNESS,
            title="Multiple columns have meaningful missingness",
            details=details,
            why_it_matters=(
                "Multiple columns with moderate missingness can collectively reduce "
                "data quality and complicate analysis."
            ),
            recommended_action=(
                "Review the affected columns. Consider imputation, removal, or "
                "accepting reduced sample size where appropriate."
            )
        ))
    else:
        # Individual findings for few columns
        for cp in medium_missing:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                dataset=ds.filename,
                category=FindingCategory.MISSINGNESS,
                title=f"High missingness in column '{cp.name}'",
                details=f"Column '{cp.name}' has {cp.missing_percentage:.1f}% missing values.",
                why_it_matters=(
                    "High missingness in important columns can bias analysis and reduce "
                    "statistical power."
                ),
                recommended_action=(
                    "Assess whether the column is critical for downstream use. Consider "
                    "imputation, removal, or accepting the reduced sample size."
                )
            ))


def compute_dataset_readiness(
    datasets: list[DatasetInfo], findings: list[Finding]
) -> list[DatasetReadinessInfo]:
    """Compute readiness status for each dataset."""
    readiness = []

    # Group findings by dataset
    findings_by_dataset: dict[str, list[Finding]] = {}
    for f in findings:
        findings_by_dataset.setdefault(f.dataset, []).append(f)

    for ds in datasets:
        ds_findings = findings_by_dataset.get(ds.filename, [])

        # Determine highest severity
        severity_order = {
            Severity.CRITICAL: 4,
            Severity.HIGH: 3,
            Severity.MEDIUM: 2,
            Severity.LOW: 1,
            Severity.INFO: 0,
        }
        highest = max((severity_order[f.severity] for f in ds_findings), default=0)
        highest_severity = Severity.INFO
        for sev, val in severity_order.items():
            if val == highest:
                highest_severity = sev
                break

        # Determine status
        if ds.parse_errors:
            status = DatasetReadiness.ERROR
        elif highest_severity == Severity.CRITICAL:
            status = DatasetReadiness.ERROR
        elif highest_severity == Severity.HIGH:
            status = DatasetReadiness.HIGH_RISK
        elif highest_severity == Severity.MEDIUM:
            status = DatasetReadiness.REVIEW
        else:
            status = DatasetReadiness.READY

        readiness.append(DatasetReadinessInfo(
            filename=ds.filename,
            status=status,
            finding_count=len(ds_findings),
            highest_severity=highest_severity,
        ))

    return readiness


def build_audit_summary(datasets: list[DatasetInfo], findings: list[Finding]) -> AuditSummary:
    """Build top-level audit summary."""
    severity_counts = {s.value: 0 for s in Severity}
    for f in findings:
        severity_counts[f.severity.value] += 1

    return AuditSummary(
        datasets_scanned=len(datasets),
        total_records=sum(d.row_count for d in datasets),
        total_columns=sum(len(d.columns) for d in datasets),
        findings_count=len(findings),
        by_severity=severity_counts,
    )

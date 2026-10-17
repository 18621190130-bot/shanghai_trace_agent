"""Staging orchestration. Boundary exclusions are retained for audit."""
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from .normalization import normalize_candidate
from .deduplication import deduplicate_candidates, record_key
from .evidence import build_evidence_bundle
from .coverage import WestBundCoverageAnalyzer
from .boundary import BOUNDS, POLYGON, REVIEW_MARGIN_M
from .discovery_scope import discovery_exclusion
from .sources.base import utc_now


def collect_sources(sources):
    raw, errors, discovery_excluded = [], [], []
    for source in sources:
        try:
            for candidate in source.collect():
                reason = discovery_exclusion(candidate)
                if reason:
                    discovery_excluded.append(dict(record_id=record_key(candidate), name=candidate.name_zh or candidate.name_en, reason=reason))
                else:
                    raw.append(candidate)
        except Exception as exc:
            # An unexpected adapter fault must not discard already yielded records.
            source.error("adapter_failure", exc)
        errors.extend(source.errors)
    normalized = []
    for candidate in raw:
        try:
            normalized.append(normalize_candidate(candidate))
        except Exception as exc:
            errors.append(dict(source=candidate.source_type, record_id=record_key(candidate),
                               status="normalization_failure", error_type=type(exc).__name__))
    excluded = [n for n in normalized if n.boundary_status == "outside_pilot"]
    eligible = [n for n in normalized if n.boundary_status != "outside_pilot"]
    canonical = deduplicate_candidates(eligible)
    bundles = [build_evidence_bundle(c) for c in canonical]
    return raw, canonical, bundles, dict(
        created_at=utc_now(), walk_zone="west_bund", stage="Phase 2.5A; human review required",
        counts=dict(provider_records=len(raw)+len(discovery_excluded), discovery_excluded=len(discovery_excluded), raw=len(raw), boundary_excluded=len(excluded), in_scope_raw=len(eligible), canonical=len(canonical)),
        raw_source_coverage=dict(Counter(r.source_type for r in raw)),
        canonical_source_coverage=dict(Counter(t for c in canonical for t in {r.source_type for r in c.merged_source_records})),
        boundary_status_counts=dict(Counter(c.boundary_status for c in canonical)),
        discovery_exclusions=discovery_excluded,
        boundary=dict(coordinate_system="GCJ-02", discovery_bbox=BOUNDS, polygon=POLYGON, review_margin_m=REVIEW_MARGIN_M,
                      rationale="Conservative envelope around existing Star Museum to Gate M cluster; not entire official waterfront or an administrative polygon.",
                      context_url="https://www.westbund.com/cn/index/NEWS-CENTER/2022-0930.html"),
        excluded_records=[dict(record_id=record_key(n.raw), name=n.name_zh or n.name_en,
                               coordinates=n.coordinates, reason="outside_pilot") for n in excluded],
        errors=errors, partial_source_failure=any(e["status"] == "partial_source_failure" for e in errors))


def write_outputs(output_dir, raw, canonical, bundles, run_report):
    root = Path(output_dir)
    outputs = {
        "raw/west_bund_raw_candidates.json": [asdict(r) for r in raw],
        "canonical/west_bund_canonical_candidates.json": [asdict(c) for c in canonical],
        "canonical/west_bund_evidence_bundles.json": [asdict(b) for b in bundles],
        "west_bund_baseline_report.json": WestBundCoverageAnalyzer().analyze(),
        "west_bund_collection_report.json": run_report,
    }
    for relative, data in outputs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

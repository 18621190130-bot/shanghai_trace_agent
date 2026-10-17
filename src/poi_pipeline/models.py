"""Source records are deliberately separate from the production POI contract."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawCandidate:
    source_candidate_id: str
    source_type: str
    source_name: str
    source_url: str
    retrieved_at: str
    name_zh: str = ""
    name_en: str = ""
    aliases: list[str] = field(default_factory=list)
    address: str = ""
    coordinates: tuple[float, float] | None = None  # latitude, longitude
    coordinate_system: str = "WGS84"
    source_category: str = ""
    raw_provider_tags: dict[str, Any] = field(default_factory=dict)
    snippets: list[dict] = field(default_factory=list)
    supports: list[str] = field(default_factory=lambda: ["identity"])
    entity_kind: str = "unknown"  # source category, never ShanghaiTrace taxonomy


@dataclass
class NormalizedCandidate:
    raw: RawCandidate
    name_zh: str
    name_en: str
    aliases: list[str]
    address: str
    coordinates: tuple[float, float] | None
    category: str
    entity_kind: str
    boundary_status: str
    issues: list[str] = field(default_factory=list)


@dataclass
class CanonicalCandidate:
    candidate_id: str
    name_zh: str
    name_en: str
    aliases: list[str]
    address: str
    coordinates: tuple[float, float] | None
    entity_kind: str
    boundary_status: str
    merged_source_records: list[RawCandidate]
    sources: list[dict]
    field_sources: dict
    issues: list[str] = field(default_factory=list)
    coordinate_system: str = "GCJ-02"
    walk_zone: str = "west_bund"
    stage: str = "unreviewed_candidate"


@dataclass
class EvidenceBundle:
    candidate_id: str
    evidence: dict[str, list[dict]]
    gaps: list[str]
    conflicts: list[str]
    enrichment_permitted: bool = False

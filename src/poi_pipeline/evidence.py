from dataclasses import asdict
from .models import EvidenceBundle
from .deduplication import record_key


def build_evidence_bundle(candidate):
    groups = {k: [] for k in ("identity", "coordinates", "map", "osm", "official", "history", "public_space", "access", "opening")}
    for raw in candidate.merged_source_records:
        base = dict(record_id=record_key(raw), source_type=raw.source_type,
                    source_name=raw.source_name, url=raw.source_url, retrieved_at=raw.retrieved_at)
        groups["identity"].append(dict(base, name_zh=raw.name_zh, name_en=raw.name_en, address=raw.address))
        if raw.coordinates:
            groups["coordinates"].append(dict(base, coordinates=raw.coordinates, coordinate_system=raw.coordinate_system))
        target = {"amap": "map", "osm": "osm", "official": "official", "government": "official"}.get(raw.source_type)
        if target:
            groups[target].append(dict(base, category=raw.source_category, provider_tags=raw.raw_provider_tags, snippets=raw.snippets))
        for snippet in raw.snippets:
            for support in snippet.get("supports", []):
                if support in groups and support not in ("map", "osm", "official", "coordinates", "identity"):
                    groups[support].append(dict(base, **snippet))
    return EvidenceBundle(candidate.candidate_id, groups, [k for k, v in groups.items() if not v], candidate.issues)

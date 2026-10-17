"""Conservative complete-link clustering; no distance-only or name-only merge."""
import hashlib
from difflib import SequenceMatcher
from ..geo_utils import haversine_km
from .models import CanonicalCandidate
from .normalization import match_key

PRIORITY = {"government": 0, "official": 1, "amap": 2, "osm": 3, "secondary": 4}


def record_key(raw):
    return f"{raw.source_type}:{raw.source_candidate_id}"


def same_entity(a, b):
    if record_key(a.raw) == record_key(b.raw):
        return True
    if a.entity_kind == "unknown" or b.entity_kind == "unknown" or a.entity_kind != b.entity_kind:
        return False
    if a.raw.source_type == b.raw.source_type == "osm":
        return False  # distinct OSM IDs may be individual tanks, galleries or floors
    if a.coordinates is None or b.coordinates is None:
        return False  # official name mentions without geometry require human linking
    distance = haversine_km(a.coordinates, b.coordinates) * 1000
    if distance > 160:
        return False
    names_a = {match_key(n) for n in [a.name_zh, a.name_en, *a.aliases] if n}
    names_b = {match_key(n) for n in [b.name_zh, b.name_en, *b.aliases] if n}
    exact = bool(names_a & names_b)
    similarity = max((SequenceMatcher(None, x, y).ratio() for x in names_a for y in names_b), default=0)
    address_match = bool(a.address and b.address and SequenceMatcher(None, match_key(a.address), match_key(b.address)).ratio() >= .85)
    return (exact and distance <= 100) or (similarity >= .90 and address_match and distance <= 160)


def deduplicate_candidates(records, zone_id='west_bund'):
    groups = []
    for item in sorted(records, key=lambda r: record_key(r.raw)):
        group = next((g for g in groups if all(same_entity(item, other) for other in g)), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    result = []
    for group in groups:
        ordered = sorted(group, key=lambda n: (PRIORITY.get(n.raw.source_type, 9), record_key(n.raw)))
        geometry = sorted(group, key=lambda n: ({"amap": 0, "osm": 1}.get(n.raw.source_type, 2), record_key(n.raw)))
        coord = next((n for n in geometry if n.coordinates is not None), None)
        fields = {}
        def choose(field):
            selected = next((n for n in ordered if getattr(n, field)), None)
            fields[field] = record_key(selected.raw) if selected else None
            return getattr(selected, field) if selected else ""
        zh, en, address = choose("name_zh"), choose("name_en"), choose("address")
        fields["coordinates"] = record_key(coord.raw) if coord else None
        raw = [n.raw for n in ordered]
        sources = [dict(source_type=r.source_type, source_name=r.source_name, url=r.source_url,
                        retrieved_at=r.retrieved_at, supports=r.supports, record_id=record_key(r)) for r in raw]
        cid = hashlib.sha256("|".join(sorted(record_key(r) for r in raw)).encode()).hexdigest()[:16]
        issues = sorted({issue for n in group for issue in n.issues})
        if len({n.address for n in group if n.address}) > 1:
            issues.append("address_variants_preserved")
        prefix = 'wb' if zone_id == 'west_bund' else zone_id
        result.append(CanonicalCandidate(prefix + "_" + cid, zh, en,
            sorted({v for n in group for v in [n.name_zh, n.name_en, *n.aliases] if v and v not in (zh, en)}),
            address, coord.coordinates if coord else None, ordered[0].entity_kind,
            coord.boundary_status if coord else "needs_review", raw, sources, fields, issues, walk_zone=zone_id))
    return result

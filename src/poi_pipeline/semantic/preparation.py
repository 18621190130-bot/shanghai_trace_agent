"""Explicit user-requested consolidation, preserving original 2.5A artifacts."""
import copy
import hashlib
import json
from ..normalization import match_key
from ...geo_utils import haversine_km

USER_GROUPS = [
    ("西岸艺术中心（含A馆）", "西岸艺术中心", {"西岸艺术中心", "西岸艺术中心A馆"}),
    ("西岸穹顶艺术中心（含北广场）", "西岸穹顶艺术中心", {"西岸穹顶艺术中心", "西岸穹顶北广场"}),
]


def prepare_candidates(candidates, bundles):
    result = copy.deepcopy(candidates)
    evidence = {b['candidate_id']: copy.deepcopy(b) for b in bundles}
    lineage = []
    for display, parent_name, names in USER_GROUPS:
        members = [c for c in result if c['name_zh'] in names]
        if not members:
            continue
        parent = next(c for c in members if c['name_zh'] == parent_name and c['coordinates'])
        merged = copy.deepcopy(parent)
        ids = sorted(c['candidate_id'] for c in members)
        merged['candidate_id'] = 'wb_group_' + hashlib.sha256('|'.join(ids).encode()).hexdigest()[:12]
        merged['name_zh'] = display
        merged['aliases'] = sorted({n for c in members for n in [c['name_zh'], c['name_en'], *c['aliases']] if n})
        merged['component_candidates'] = [dict(candidate_id=c['candidate_id'], name=c['name_zh'], coordinates=c['coordinates']) for c in members]
        merged['consolidation_basis'] = 'explicit_user_instruction_2026-10-04; route-node grouping, not assertion that plaza and venue are identical'
        merged['merged_source_records'] = unique([r for c in members for r in c['merged_source_records']])
        merged['sources'] = unique([s for c in members for s in c['sources']])
        merged['issues'] = sorted({i for c in members for i in c['issues']} | {'composite_scope_needs_visit_review'})
        merged_bundle = dict(candidate_id=merged['candidate_id'], evidence={}, gaps=[], conflicts=merged['issues'])
        for group in evidence[ids[0]]['evidence']:
            merged_bundle['evidence'][group] = unique([r for cid in ids for r in evidence[cid]['evidence'][group]])
        merged_bundle['gaps'] = [g for g, v in merged_bundle['evidence'].items() if not v]
        evidence[merged['candidate_id']] = merged_bundle
        result = [c for c in result if c['candidate_id'] not in ids] + [merged]
        lineage.append(dict(merged_id=merged['candidate_id'], name=display, member_ids=ids,
                            coordinate_source_candidate=parent['candidate_id'], basis=merged['consolidation_basis']))
    return result, {c['candidate_id']: evidence[c['candidate_id']] for c in result}, lineage


def unique(values):
    seen, result = set(), []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def evidence_catalog(bundle):
    """Assign granular deterministic refs, retaining original source and support type."""
    catalog = {}
    for group, records in bundle['evidence'].items():
        for record in records:
            base = {k: record.get(k) for k in ('record_id', 'source_type', 'source_name', 'url', 'retrieved_at')}
            atoms = []
            if group == 'identity':
                atoms = [(k, record[k]) for k in ('name_zh', 'name_en', 'address') if record.get(k)]
            elif group == 'coordinates':
                atoms = [('coordinates', dict(coordinates=record['coordinates'], coordinate_system=record['coordinate_system']))]
            elif group in ('map', 'osm', 'official'):
                if record.get('category'):
                    atoms.append(('category', record['category']))
                for k, v in record.get('provider_tags', {}).items():
                    if k in ('tourism', 'historic', 'leisure', 'amenity', 'man_made', 'description', 'opening_hours', 'access', 'name', 'name:en', 'name:zh', 'artwork_type', 'artist_name', 'start_date', 'building', 'type', 'typecode'):
                        atoms.append((k, str(v)))
                atoms += [('snippet', s['text']) for s in record.get('snippets', [])]
            elif record.get('text'):
                atoms = [('snippet', record['text'])]
            for field, value in atoms:
                atom = dict(base, group=group, field=field, value=value)
                ref = 'e_' + hashlib.sha256(json.dumps(atom, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
                catalog[ref] = atom
    return catalog


def geographic_context(candidate, candidates, production):
    point = candidate['coordinates']
    if not point:
        return dict(location_confidence='low', nearest_candidates=[], nearest_production=[], fills_spatial_gap=None,
                    basis='coordinates missing; no inferred position')
    nearby = sorted((dict(candidate_id=c['candidate_id'], name=c['name_zh'] or c['name_en'],
                          distance_m=round(haversine_km(point, c['coordinates'])*1000))
                     for c in candidates if c['candidate_id'] != candidate['candidate_id'] and c['coordinates']),
                    key=lambda x: x['distance_m'])[:4]
    existing = sorted((dict(poi_id=p.id, name=p.name_zh, distance_m=round(haversine_km(point, p.coordinates)*1000))
                       for p in production if p.coordinates), key=lambda x: x['distance_m'])
    gap = False
    if len(existing) >= 2:
        a, b = existing[:2]
        pa, pb = (next(p for p in production if p.id == item['poi_id']) for item in (a, b))
        direct = haversine_km(pa.coordinates, pb.coordinates)*1000
        gap = a['distance_m'] >= 150 and direct > 0 and (a['distance_m']+b['distance_m']) <= 1.25*direct
    return dict(location_confidence='medium' if candidate['boundary_status']=='needs_review' else 'high',
                nearest_candidates=nearby, nearest_production=existing[:2], fills_spatial_gap=gap,
                basis='Haversine approximation between representative points; no walking routing or verified access')


def duplicate_context(candidate, candidates, production):
    names = {match_key(v) for v in [candidate['name_zh'], candidate['name_en'], *candidate['aliases']] if v}
    production_matches = []
    point = candidate['coordinates']
    for poi in production:
        if point and names & {match_key(poi.name_zh), match_key(poi.name_en)} and haversine_km(point, poi.coordinates) < .2:
            production_matches.append(poi.id)
    possible = []
    for other in candidates:
        if other['candidate_id'] == candidate['candidate_id']:
            continue
        other_names = {match_key(v) for v in [other['name_zh'], other['name_en'], *other['aliases']] if v}
        if names & other_names:
            distance = haversine_km(point, other['coordinates'])*1000 if point and other['coordinates'] else None
            if distance is None or distance < 250:
                possible.append(dict(candidate_id=other['candidate_id'], name=other['name_zh'] or other['name_en'], distance_m=distance))
    return dict(existing_production_ids=production_matches, possible_candidate_duplicates=possible)

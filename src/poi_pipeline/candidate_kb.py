"""Deterministic promotion preview from approved route nodes, not provider objects."""
import copy
from collections import Counter
from .semantic.final_review import CINEMA

# Versioned identity allocation, independent of array order. Never renumber existing IDs.
NEW_IDS = {'route:art_center': 'p36', 'route:dome': 'p37', 'route:skate': 'p38',
    'route:runway': 'p39', 'route:photography': 'p40',
    'route:wb_7ca7f91efb488c29': 'p41', 'route:wb_72b583ec31ffce20': 'p42',
    'route:wb_fd436a54b9d249a2': 'p43'}
ENGLISH = dict(zip(NEW_IDS, ('West Bund Art Center', 'West Bund Dome Art Center (including North Plaza)',
    'Riverside Skateboard Park', 'Xuhui Runway Park', 'Shanghai Center of Photography',
    'West Bund Theatre', 'Xuhui Riverside Maritime Tower Square', 'Beipiao Wharf Crane')))


def build_candidate_kb(production, staging, final_review):
    kb = copy.deepcopy(production)
    nodes = staging['route_nodes']
    existing = {p['id']: p for p in kb['pois']}
    mapping = {}
    zone = next(z for z in kb['metadata']['walk_zones'] if z['id'] == 'west_bund')
    for row in nodes:
        if not row['route_selectable'] or row['decision'] != 'recommended_accept':
            raise ValueError('unapproved staging route node')
        nid = row['node_id']
        if nid.startswith('production:'):
            pid = row['production_match']
            poi = existing[pid]
            if pid not in ('p5', 'p28', 'p29', 'p30', 'p31'):
                raise ValueError('unexpected existing West Bund identity')
        else:
            pid = NEW_IDS[nid]
            if pid in existing:
                raise ValueError('new stable ID collision')
            category = row['category']
            category = category if isinstance(category, dict) else {'zh': category, 'en': category}
            labels = {'cultural_venue': '文化场馆', 'performance_venue': '演艺场馆',
                'park': '公园', 'public_space': '公共空间', 'industrial_heritage': '工业遗存',
                'museum': '艺术展馆', 'art_venue': '艺术场馆'}
            if category['zh'] == category['en']:
                category['zh'] = labels.get(category['en'], '文化与公共空间')
            profile = row['visit_profile']
            modes = {m: copy.deepcopy(profile[m]) for m in ('walk_stop', 'full_visit') if profile.get(m)}
            summary = row['summary']
            summary = summary.get('text') if isinstance(summary, dict) else summary
            kind = 'park' if nid in ('route:skate', 'route:runway') else 'landmark' if row['primary_role'] == 'transition_stop' else 'venue'
            environment = 'indoor' if nid == 'route:photography' else 'mixed' if nid == 'route:wb_7ca7f91efb488c29' else 'outdoor'
            aliases = list(dict.fromkeys(row.get('aliases', []) + [e['name'] for e in final_review['source_entities']
                if e['parent_node'] == nid and e['name'] != row['name']]))
            poi = dict(id=pid, name={'zh': row['name'], 'en': ENGLISH[nid], 'aliases': aliases},
                location=dict(address_zh=next((e['value'] for e in row['evidence_catalog'].values()
                    if e.get('field') == 'address' and isinstance(e.get('value'), str) and e['value']), ''),
                    lat=row['coordinates'][0], lng=row['coordinates'][1],
                    coordinate_system='GCJ-02', coordinate_note='Approximate representative route anchor, not a surveyed entrance. '+row.get('coordinate_selection', {}).get('reason', 'Inherited approved staging point.')),
                walk_zone=dict(id='west_bund', name_zh=zone['name_zh'], name_en=zone['name_en']),
                category=copy.deepcopy(category), tags={g: copy.deepcopy(row[g]) for g in ('interest_tags', 'experience_tags', 'culture_tags')},
                planning=dict(environment=environment, crowd_level_default=None, ticket_required=None,
                    reservation_required=None, opening_hours=None, opening_hours_source=None, last_verified=None),
                content=dict(summary_zh=summary or row['name']), culture_bridge=copy.deepcopy(row['culture_bridge']),
                verification=dict(status='human_approved_candidate_staging', source='Phase 2.5B final human review',
                    source_confidence=row['source_confidence'], semantic_confidence=row['semantic_confidence'],
                    note='Current opening, entry and ticket availability remain unverified; admission is not a live access guarantee.'),
                poi_type=kind, visit_profile=dict(default_mode='walk_stop', supported_modes=list(modes), modes=modes),
                visit_profile_calibration=dict(time_basis='product_planning_estimate', pending_manual_calibration_modes=list(modes)),
                visit_mode_details={m: dict(environment='mixed' if m == 'full_visit' else environment,
                    ticket_required=None, scope=(row['visit_scope'][m] if isinstance(row.get('visit_scope'), dict) and m in row['visit_scope'] else profile.get('scope', row['name']))) for m in modes},
                source_provenance=dict(staging_node_id=nid, sources=copy.deepcopy(row['sources']),
                    evidence_catalog=copy.deepcopy(row['evidence_catalog']), tag_evidence=copy.deepcopy(row.get('tag_evidence', [])),
                    coordinate_observations=copy.deepcopy(row['coordinate_observations']),
                    boundary_status=row['boundary_status'], scope_decision=row.get('scope_decision'),
                    coordinate_selection=copy.deepcopy(row.get('coordinate_selection'))))
            kb['pois'].append(poi)
        poi.update(route_role={'primary': row['primary_role'], 'eligible': row['eligible_roles']},
                   route_selectable=True, counts_as_route_stop=True)
        mapping[nid] = pid
    if set(mapping) != {*(f'production:{pid}' for pid in ('p5', 'p28', 'p29', 'p30', 'p31')), *NEW_IDS}:
        raise ValueError('final active route node identity set disagrees with approved baseline')
    for order, poi in enumerate(kb['pois'], 1):
        poi['display_order'] = order
    counts = Counter(p['walk_zone']['id'] for p in kb['pois'])
    kb['metadata'].update(poi_count=len(kb['pois']), version='phase2.5c-candidate-only',
        candidate_kb_status='pending_validation', production_imported=False)
    for declared in kb['metadata']['walk_zones']:
        declared['poi_count'] = counts[declared['id']]
    kb['route_engine_defaults']['route_composition_enabled_zones'] = ['west_bund']
    entities = copy.deepcopy(final_review['source_entities'])
    for e in entities:
        e.update(counts_as_route_stop=False, route_selectable=False,
                 parent_candidate_poi_id=mapping.get(e['parent_node']))
    cinema = copy.deepcopy(next(r for r in final_review['rows'] if r['node_id'] == CINEMA))
    cinema.update(decision='reject_current_pilot', route_selectable=False, counts_as_route_stop=False,
        counts_as_new_stop=False, conditional_acceptance={'required': False, 'status': 'rejected_current_pilot'},
        review_group='F', reason=['用户补充确认地图/手机搜索无法找到；本阶段移出active pilot，不删除历史provenance。'])
    return kb, dict(staging_to_candidate_id=mapping, internal_entities=entities,
                    historical_rejected_candidates=[cinema], active_conditional_candidates=[])

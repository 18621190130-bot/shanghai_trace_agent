"""Human decisions for staging only; no provider or route-engine dependency."""
import copy
from collections import Counter
from ..boundary import boundary_status

GROUPS = ('interest_tags', 'experience_tags', 'culture_tags')
CRANE = 'route:wb_fd436a54b9d249a2'
MARITIME = 'route:wb_72b583ec31ffce20'
CINEMA = 'route:wb_d7d1677306fa4d92'
THEATRE = 'route:wb_7ca7f91efb488c29'
CHILDREN = {'route:wb_325c03999db02641': 'route:art_center',
            'route:wb_bfd5b11fdae241d1': CRANE}
ACCEPTED = {'route:art_center', 'route:dome', 'route:skate',
            'route:runway', 'route:photography', CRANE}
CONDITIONS = {MARITIME: ('public_access', 'representative_coordinate'),
              CINEMA: ('current_existence', 'public_access', 'long_term_stability'),
              THEATRE: ('current_existence', 'stable_public_venue', 'purposeful_visit',
                        'arrival_scenario', 'independent_citywalk_value')}
FIXED_TAGS = {
    'route:skate': (['parks', 'waterfront'], ['riverside_walk', 'social_observation'], ['public_life']),
    'route:runway': (['parks', 'history'], ['adaptive_reuse', 'street_scene'], ['urban_renewal']),
    'route:photography': (['art', 'architecture'], ['museum_visit'], []),
    MARITIME: (['waterfront'], ['riverside_walk'], []),
    CRANE: (['industrial_heritage', 'waterfront'], ['riverside_walk'], []),
    CINEMA: (['art'], ['photogenic'], []),
    THEATRE: (['art'], [], []),
}


def condition_passed(node_id, verification):
    checks = verification.get(node_id, {}).get('checks', {})
    return all(checks.get(k, {}).get('status') == 'confirmed'
               and checks[k].get('evidence_refs') for k in CONDITIONS[node_id])


def build_final_review(rows, nodes, entities, verification, taxonomy):
    """Apply explicit decisions, retaining evidence and all source identities."""
    rows, nodes, entities = copy.deepcopy((rows, nodes, entities))
    raw = {n['node_id']: n for n in nodes}
    by_id = {r['node_id']: r for r in rows}
    for child_id, parent_id in CHILDREN.items():
        child, parent = by_id[child_id], by_id[parent_id]
        parent['sources'] += child['sources']
        parent['evidence_catalog'].update(child['evidence_catalog'])
        parent['member_candidate_ids'] += child['member_candidate_ids']
        parent['internal_entity_ids'] += child['member_candidate_ids']
        parent.setdefault('aliases', []).append(child['name'])
        for e in entities:
            if e['parent_node'] == child_id:
                e.update(parent_node=parent_id, relationship='human_confirmed_internal_entity')
        entities.append(dict(entity_id=child_id, name=child['name'], parent_node=parent_id,
                             relationship='human_confirmed_internal_entity',
                             route_selectable=False, counts_as_new_stop=False,
                             decision='internal', sources=child['sources'],
                             evidence_catalog=child['evidence_catalog'],
                             reason='人工确认：仅保留在父节点，不增加独立 stop。'))

    result = []
    for r in rows:
        nid = r['node_id']
        if nid in CHILDREN:
            continue
        semantic = r.pop('semantic', {})
        r['previous_review_ref'] = 'repair/west_bund_review_repaired.json#' + nid
        r['human_review_basis'] = 'Phase 2.5B 最终人工审核落地：用户明确决定'
        r['stage'] = 'final_human_review_staging'
        r['production_imported'] = False
        r['boundary_status'] = raw[nid]['boundary_status']
        r['tag_evidence'] = semantic.get('tag_evidence', [])
        snapshot = r.get('production_snapshot', {})
        r['summary'] = semantic.get('summary_draft') or snapshot.get('content', {}).get('summary_zh')
        r['culture_bridge'] = semantic.get('culture_bridge_draft') or r.get('production_snapshot', {}).get('culture_bridge')
        r['citywalk_value'] = semantic.get('citywalk_value', {'level': 'high', 'reason': 'existing production snapshot'})
        r['factual_fields'] = semantic.get('factual_fields', {})
        r['planning'] = {'opening_hours': None, 'ticket_prices': None,
                         'reservation_requirements': None, 'current_access': 'unknown'}
        r['visit_profile_calibration'] = snapshot.get('visit_profile_calibration',
            {'time_basis': 'product_planning_estimate'})
        r['counts_as_new_stop'] = False
        production = r['identity_status'] == 'existing_production'
        v = verification.get(nid)
        if v:
            r['targeted_verification'] = copy.deepcopy(v)
            r['sources'] += v.get('sources', [])
            r['evidence_catalog'].update(v.get('evidence_catalog', {}))
            if v.get('representative_anchor'):
                anchor = v['representative_anchor']
                r['coordinates'] = list(anchor['coordinates'])
                r['coordinate_selection'] = copy.deepcopy(anchor)
                r['boundary_status'] = boundary_status(r['coordinates'])
                r['geographic_context'] = {'location_confidence': anchor['confidence'],
                    'basis': 'representative anchor changed; previous nearest distances invalidated',
                    'walking_routing_verified': False}
        conditional = nid in CONDITIONS
        passed = condition_passed(nid, verification) if conditional else False
        accepted = production or nid in ACCEPTED or passed
        r['conditional_acceptance'] = dict(required=conditional,
            status='passed' if passed else 'pending' if conditional else 'not_applicable')
        r['decision_before_human_review'] = r['decision']
        r['decision'] = 'recommended_accept' if accepted else 'reject' if r['decision'] == 'reject' else 'defer'
        r['route_selectable'] = accepted
        r['counts_as_new_stop'] = accepted and not production
        r['review_group'] = 'A' if production else 'B' if accepted else 'D' if conditional else 'F' if r['decision'] == 'reject' else 'E'
        role = 'anchor' if production else 'transition_stop' if nid in (CRANE, MARITIME, CINEMA) else r['primary_role']
        if nid in ACCEPTED - {CRANE} or nid == THEATRE:
            role = 'supporting_stop'
        if accepted and role == 'transition_stop':
            r['review_group'] = 'C'
        rr = r['route_role']
        rr.update(primary=role, eligible=['anchor', 'supporting_stop'] if production and
                  'walk_stop' in r.get('visit_profile', {}).get('supported_modes', []) else [role])
        r.update(primary_role=role, eligible_roles=rr['eligible'])
        if nid in FIXED_TAGS:
            for group, tags in zip(GROUPS, FIXED_TAGS[nid]):
                r[group] = list(tags)
        r['reason'] = ['人工接受既有 production anchor；不计新增。' if production else
            '人工接受一个独立 staging 节点。' if nid in ACCEPTED else
            '定向核验通过人工指定的全部条件，接受 staging 节点。' if passed else
            '条件核验未通过：' + ', '.join(k for k in CONDITIONS[nid] if
                v is None or v.get('checks', {}).get(k, {}).get('status') != 'confirmed') if conditional else
            '维持人工 reject：' + ' '.join(r['reason']) if r['decision'] == 'reject' else
            '人工 defer；不计可选 stop，不表示永久 reject。']
        if v:
            r['reason'].append(v['conclusion'])
        if nid == 'route:runway':
            r['scope_decision'] = 'human_accepted_existing_150m_review_margin; polygon_unchanged'
        if nid == 'route:dome':
            r['node_model'] = 'one_node_dual_mode'
            r['visit_scope'] = {'walk_stop': '北广场及场馆外部公共空间，短暂停留',
                'full_visit': '场馆内部/演出文化访问；仅在另行核实活动及入场条件时使用'}
            r['mode_access'] = {'walk_stop': 'human_accepted_exterior_scope', 'full_visit': 'unknown'}
        if v and v.get('checks', {}).get('public_access', {}).get('status') == 'confirmed':
            r['source_confidence']['current_access'] = 'medium'
            r['access_scope'] = '外部公众停留/观察区域；不保证实时无临时管制，不包含塔体/场馆内部许可。'
        if nid == THEATRE and passed:
            r['source_confidence']['current_access'] = 'medium'
            r['access_scope'] = '官方购票观演或预约参观导览；到访前核实当日安排，不假设全天免费入内。'
            r['semantic_confidence'] = 'medium'
            rr.update(confidence='medium', reason='官方有演出购票、参观导览与龙腾大道2290号到访场景，可独立有目的访问；与邻近强节点形成补充。',
                independent_destination_value='medium', route_connector_value='medium',
                alternatives_reason={'anchor': '可独立观演，但本试点作为补充节点；未核实可承载路线主主题的固定访问内容。',
                    'supporting_stop': '有独立观演/预约导览价值。', 'transition_stop': '并非仅用于连接邻近节点，具备有目的地文化访问场景。'})
            r['role_confidence'] = 'medium'
            r['summary'] = {'text': '龙腾大道2290号的公共演艺场馆，可按官方安排购票观演或预约参观导览。当前可订场次和入场条件须另核实。',
                            'evidence_refs': ['fv_theatre_services', 'fv_theatre_license']}
            r['tag_evidence'] = [{'group': 'interest_tags', 'tag': 'art', 'evidence_refs': ['fv_theatre_services', 'fv_theatre_license']}]
            r['visit_profile']['scope'] = 'walk_stop 产品估时仅适用另行确认的参观范围；观演时长取实际节目，不推定免费或随时入内。'
        for group in GROUPS:
            r[group] = list(dict.fromkeys(r[group]))
        # Previous proposals remain in the immutable repair artifact, not contradictory nested fields.
        for key in ('targeted_answers', 'tag_changes', 'role_changes', 'tag_audit_status', 'role_evidence_refs'):
            r.pop(key, None)
        result.append(r)
    for e in entities:
        e.update(route_selectable=False, counts_as_new_stop=False)
        if e['name'].startswith('岩时攀岩'):
            e.update(decision='reject', reason='人工维持 reject：内部普通运动商户，无独立 City Walk stop 价值。')
        e.setdefault('decision', 'internal')
    selectable = [copy.deepcopy(r) for r in result if r['route_selectable']]
    stats = dict(existing_anchor=sum(r['review_group'] == 'A' for r in result),
                 new_supporting_stop=sum(r['review_group'] == 'B' for r in result),
                 new_transition_stop=sum(r['review_group'] == 'C' for r in result),
                 conditional=sum(r['review_group'] == 'D' for r in result),
                 conditional_verified=sum(r['conditional_acceptance']['status'] == 'passed' for r in result),
                 total_route_selectable=len(selectable), groups=dict(Counter(r['review_group'] for r in result)))
    validate_final_review(result, selectable, entities, verification, taxonomy)
    return dict(rows=result, source_entities=entities, counts=stats), selectable


def validate_final_review(rows, selectable, entities, verification, taxonomy):
    """Fail closed on admission, identity, taxonomy and coordinate provenance."""
    if len({r['node_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate route nodes')
    expected = {r['node_id'] for r in rows if r['route_selectable']}
    if expected != {r['node_id'] for r in selectable} or len(expected) != len(selectable):
        raise ValueError('selectable set mismatch')
    if any(e['route_selectable'] or e['counts_as_new_stop'] for e in entities):
        raise ValueError('internal entity counts as stop')
    if any(r['node_id'] in CHILDREN for r in rows):
        raise ValueError('child in main review')
    member_ids = [cid for r in rows for cid in r['member_candidate_ids']]
    if len(member_ids) != len(set(member_ids)):
        raise ValueError('source candidate assigned twice')
    for r in rows:
        nid = r['node_id']
        if r['route_selectable'] != (r['decision'] == 'recommended_accept'):
            raise ValueError('decision/selectability mismatch')
        if nid in CONDITIONS and r['route_selectable'] and not condition_passed(nid, verification):
            raise ValueError('unverified conditional node selected')
        if r['counts_as_new_stop'] != (r['route_selectable'] and r['identity_status'] != 'existing_production'):
            raise ValueError('incorrect new stop count')
        rr = r['route_role']
        if rr['primary'] not in ('anchor', 'supporting_stop', 'transition_stop') or rr['primary'] not in rr['eligible']:
            raise ValueError('invalid route role')
        if r['primary_role'] != rr['primary'] or r['eligible_roles'] != rr['eligible']:
            raise ValueError('inconsistent role fields')
        for group in GROUPS:
            if len(r[group]) != len(set(r[group])) or any(t not in taxonomy[group] for t in r[group]):
                raise ValueError('unknown or duplicate tag')
        if nid in FIXED_TAGS and tuple(r[g] for g in GROUPS) != FIXED_TAGS[nid]:
            raise ValueError('human tag decision changed')
        if r['route_selectable'] and (not r['coordinates'] or r['coordinate_system'] != 'GCJ-02'):
            raise ValueError('missing inherited coordinates')
        v = verification.get(nid, {})
        refs = set(r['evidence_catalog'])
        if any(ref not in refs for check in v.get('checks', {}).values() for ref in check.get('evidence_refs', [])):
            raise ValueError('verification reference missing')
        if r.get('coordinate_selection'):
            a = r['coordinate_selection']
            if a['coordinates'] != r['coordinates'] or not a['evidence_refs'] or any(ref not in refs for ref in a['evidence_refs']):
                raise ValueError('anchor provenance missing')
            if not any(r['evidence_catalog'][ref].get('coordinates') == a['coordinates']
                       for ref in a['evidence_refs']):
                raise ValueError('anchor not equal to provider coordinate evidence')
        if r['route_selectable'] and r['boundary_status'] == 'outside_pilot':
            raise ValueError('outside pilot selected')


def zone_expansion_diagnostic(regression=None):
    """Consume future attributed outcomes; never execute regression or infer supply from tags."""
    metrics = ('theme_failure_count', 'insufficient_route_count', 'composition_failure_count',
               'candidate_pool_sizes', 'non_museum_route_success', 'parks_public_space_route_success',
               'geographic_gap_indicators')
    result = dict(status='not_run' if regression is None else 'evaluated',
                  zone_expansion_recommended=None if regression is None else False,
                  **{key: None if regression is None else regression.get(key) for key in metrics})
    if regression is not None:
        causes = regression.get('failure_causes', {})
        supply = sum(causes.get(k, 0) for k in ('quality_node_shortage', 'geographic_gap'))
        total = sum(causes.values())
        result['zone_expansion_recommended'] = total > 0 and supply > total / 2
        result['basis'] = 'Majority of failures explicitly attributed to quality node shortage/geographic gaps; unknown and algorithm causes count against expansion.'
    return result

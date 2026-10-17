"""Admission and priority are separate from semantic truth and production data."""
from collections import Counter
from .preparation import duplicate_context


def source_confidence(candidate):
    kinds = {s['source_type'] for s in candidate['sources']}
    authority = bool(kinds & {'government','official'})
    mapped = bool(kinds & {'amap','osm'})
    return dict(overall='high' if authority and mapped else 'medium' if authority or mapped else 'low',
                existence='high' if 'amap' in kinds or authority else 'medium' if 'osm' in kinds else 'low',
                authority='high' if authority else 'medium' if 'amap' in kinds else 'low',
                source_types=sorted(kinds), current_operation_verified=False)


def evaluate_citywalk_candidate(candidate, semantic, geography, duplicates):
    source = source_confidence(candidate)
    factors = dict(source_confidence=source, location_confidence=geography['location_confidence'],
                   geographic_usefulness=geography, duplication=duplicates,
                   citywalk_value=semantic['citywalk_value']['level'] if semantic else 'unknown',
                   semantic_value=semantic['semantic_confidence'] if semantic else 'unknown',
                   stability=semantic['stability'] if semantic else 'unknown')
    reject, review = [], []
    if candidate['boundary_status']=='outside_pilot':
        reject.append('outside_west_bund_pilot')
    if duplicates['existing_production_ids']:
        reject.append('duplicate_existing_production:' + ','.join(duplicates['existing_production_ids']))
    if semantic:
        if semantic.get('rejected_tag_proposals'):
            review.append('unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance')
        if semantic['category'] in ('generic_cafe','generic_restaurant','ordinary_shop','temporary_event'):
            reject.append('generic_service_or_temporary_event')
        if semantic['stability']=='temporary':
            reject.append('temporary_not_stable_route_node')
        if semantic['citywalk_value']['level']=='low' and semantic['route_role']['route_connector_value']=='low':
            reject.append('no_evidenced_independent_or_connector_citywalk_value')
        if semantic['category']=='unknown':
            review.append('unresolved_category')
        if semantic['semantic_confidence']=='low':
            review.append('low_semantic_confidence')
        if semantic['stability']=='unknown':
            review.append('stability_unknown')
        if not (semantic['interest_tags'] or semantic['experience_tags']):
            review.append('no_evidenced_interest_or_experience_tag')
        if semantic['route_role']['confidence']=='low':
            review.append('low_role_confidence')
    else:
        review.append('enrichment_failed_not_a_negative_place_verdict')
    if not candidate['coordinates']:
        review.append('missing_coordinates')
    if candidate['boundary_status']=='needs_review':
        review.append('boundary_or_location_needs_review')
    if duplicates['possible_candidate_duplicates']:
        review.append('possible_duplicate_or_nested_identity_requires_human_linking')
    if source['overall']=='low':
        review.append('weak_source_support')
    if candidate.get('component_candidates'):
        review.append('user_grouped_node_visit_scope_needs_review')
    status = 'reject' if reject else 'review' if review else 'accept'
    return dict(decision=status, meaning='recommended_for_human_review_only' if status=='accept' else 'staging_disposition_only',
                reasons=reject+review if reject or review else ['evidenced_stable_citywalk_candidate_with_location'],
                factors=factors, production_imported=False)


def marginal_coverage_gain(semantic, baseline):
    tags = {g: semantic[g] if semantic else [] for g in baseline['coverage']}
    contributions = {g: {tag: round(1/(1+baseline['coverage'][g]['frequency'][tag]), 4) for tag in assigned}
                     for g,assigned in tags.items()}
    return dict(score=round(sum(sum(v.values()) for v in contributions.values()),4), per_tag=contributions,
                newly_covered={g:[t for t in assigned if baseline['coverage'][g]['frequency'][t]==0] for g,assigned in tags.items()},
                definition='sum 1/(1+baseline frequency), fixed-baseline marginal priority; not additive portfolio utility',
                truth_effect='none; computed after semantic validation')


def coverage_preview(rows, baseline):
    accepted = [r for r in rows if r['decision']=='accept' and r['semantic']]
    result = {}
    for group, data in baseline['coverage'].items():
        added = Counter(tag for row in accepted for tag in row['semantic'][group])
        result[group] = {tag: dict(before=n, proposed_after=n+added[tag], delta=added[tag]) for tag,n in data['frequency'].items()}
    return dict(scenario='baseline + recommended accept only; no production write; review/reject excluded',
                baseline_poi_count=baseline['poi_count'], proposed_additions=len(accepted),
                proposed_poi_count=baseline['poi_count']+len(accepted), coverage=result,
                role_distribution=dict(Counter(r['route_role']['primary'] for r in rows if r['decision']!='reject' and r['semantic'])),
                unresolved_role_count=sum(r['decision']!='reject' and r['semantic'] is None for r in rows),
                accepted_role_distribution=dict(Counter(r['route_role']['primary'] for r in accepted)),
                art_without_museum=[r['candidate_id'] for r in rows if r['semantic'] and 'art' in r['semantic']['interest_tags'] and 'museum_visit' not in r['semantic']['experience_tags']],
                non_museum_art_proposals=[r['candidate_id'] for r in rows if r['semantic'] and r['semantic']['category'] in ('public_art','public_space','park','architecture','heritage')
                    and 'art' in r['semantic']['interest_tags'] and 'museum_visit' not in r['semantic']['experience_tags']],
                warning='Review identities and evidence before considering adoption. A map category is not independent cultural verification.')

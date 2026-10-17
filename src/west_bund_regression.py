"""Fixed request fixtures isolate data and routing from language parsing."""
from collections import Counter
from dataclasses import asdict
from .models import RouteRequest
from .route_engine import RouteEngine
from .route_entry import RouteEntryService
from .intent_models import RouteIntent, RouteMode
from .poi_pipeline.semantic.final_review import zone_expansion_diagnostic


def cases():
    fixtures = [
        ('A', 'art; no museums', 180, ['art'], [], [], ['museum_visit']),
        ('B', 'parks + waterfront + public life', 150, ['parks', 'waterfront'], [], ['public_life'], []),
        ('C', 'industrial heritage + waterfront', 180, ['industrial_heritage', 'waterfront'], [], [], []),
        ('D', 'architecture + art + photography-related viewing', 180, ['architecture', 'art'], ['photogenic'], [], []),
        ('E', 'modern city + waterfront', 150, ['modern_city', 'waterfront'], [], [], []),
        ('F', 'art + waterfront + industrial heritage', 180, ['art', 'waterfront', 'industrial_heritage'], [], [], []),
        ('G', 'waterfront + parks; no museums', 180, ['waterfront', 'parks'], [], [], ['museum_visit']),
        ('H', 'three-hour West Bund; no theme; no museums', 180, [], [], [], ['museum_visit']),
    ]
    return [(name, label, RouteRequest(minutes, preferred_zone='west_bund', interest_tags=interest,
        experience_tags=experience, culture_tags=culture, avoid_tags=avoid))
        for name, label, minutes, interest, experience, culture, avoid in fixtures]


def describe(engine, request, name, label):
    plan = engine.generate_route(request)
    zone = plan.selected_zone or request.preferred_zone
    before = [p for p in engine.repository.get_pois_by_zone(zone) if p.counts_as_route_stop]
    eligible = [p for p in before if p.coordinates and not engine._avoided(p, request)
                and engine.visits.resolve(p, request) is not None]
    relevant = [p for p in eligible if engine._relevant(p, request)]
    negative = all(not engine._avoided(engine.repository.get_poi_by_id(n.poi_id), request) for n in plan.ordered_pois)
    minimum = len(plan.ordered_pois) >= 3
    composition = plan.composition_diagnostics
    if plan.status == 'composition_failure':
        cause = 'route_role_composition'
    elif not minimum:
        cause = 'insufficient_high_quality_poi_supply' if len(relevant) < 3 else 'scoring_or_budget_constraint'
    else:
        cause = None
    stops = [dict(poi_id=s.poi_id, name=s.name_zh, primary_role=s.effective_primary_role,
        matched_tags=s.matched_tags, visit_mode=s.selected_visit_mode,
        estimated_visit_minutes=s.estimated_stay_minutes) for s in plan.ordered_pois]
    if len({s['poi_id'] for s in stops}) != len(stops) or any(not engine.repository.get_poi_by_id(s['poi_id']).counts_as_route_stop for s in stops):
        raise AssertionError('fake route richness')
    if not negative or (plan.total_estimated_minutes or 0) > request.available_minutes:
        raise AssertionError('hard constraints broken')
    if plan.status == 'success' and minimum and composition.get('enabled') and not composition.get('route_composition_passed'):
        raise AssertionError('invalid complete composition')
    return dict(case=name, label=label, request=asdict(request), avoid_tags=request.avoid_tags,
        matched_tags={g: sorted({t for s in plan.ordered_pois for t in s.matched_tags[g]})
                      for g in ('interest_tags', 'experience_tags', 'culture_tags')},
        candidate_pool_before_filtering=[p.id for p in before],
        candidate_pool_after_filtering=[p.id for p in eligible], relevant_candidate_pool=[p.id for p in relevant],
        selected_stops=stops, total_estimated_time=plan.total_estimated_minutes,
        time_utilization=plan.time_utilization_ratio, minimum_viable_passed=minimum,
        composition_passed=composition.get('route_composition_passed'), negative_preference_passed=negative,
        route_status=plan.status if minimum or plan.status != 'success' else 'insufficient_route',
        failure_reason=plan.errors if plan.errors else ([] if minimum else ['fewer than three suitable stops']),
        failure_attribution=cause, composition_diagnostics=composition,
        distance_method=plan.distance_method, estimated_max_single_leg_km=plan.estimated_max_single_leg_km)


def run_regression(repository):
    engine = RouteEngine(repository)
    rows = [describe(engine, req, name, label) for name, label, req in cases()]
    # A deliberately narrow theme is expected to expose the audited-role conflict, not get filler.
    a = rows[0]
    if a['route_status'] != 'composition_failure' or not a['minimum_viable_passed'] or a['composition_passed']:
        raise AssertionError('art-only no-museums must expose the anchor gap without concealing it')
    if any(r['route_status'] != 'success' or not r['minimum_viable_passed'] or not r['composition_passed'] for r in rows[1:]):
        raise AssertionError('one or more broad supported West Bund requests did not yield a viable composition')
    service = RouteEntryService(repository)
    plans = service.generate(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone='west_bund',
        interest_tags=['waterfront', 'parks'], avoid_tags=['museum_visit']))
    places = service.generate(service.places_intent(['p42', 'p43'], available_minutes=180, preferred_zone='west_bund'))
    surprise = service.generate(RouteIntent(RouteMode.SURPRISE_ME, available_minutes=180, preferred_zone='west_bund',
        start_lat=31.164519, start_lng=121.464321, avoid_tags=['museum_visit'], surprise_seed=25))
    if {s.poi_id for s in places.route_plan.ordered_pois} != {'p42', 'p43'}:
        raise AssertionError('explicit places changed or anchor silently inserted')
    if plans.status != 'success' or surprise.status != 'success':
        raise AssertionError('three mode regression failed')
    modes = {name: {'status': result.status, 'intent': result.intent.to_dict(),
                    'route_plan': result.route_plan.to_dict() if result.route_plan else None}
             for name, result in [('plan_for_me', plans), ('places_in_mind', places), ('surprise_me', surprise)]}
    return rows, modes


def expansion_diagnostics(repository, rows):
    nodes = repository.get_pois_by_zone('west_bund')
    # Fixed latitude thirds of existing pilot extent, not a new geographic boundary.
    bands = {'north': [], 'central': [], 'south': []}
    for p in nodes:
        band = 'north' if p.coordinates[0] >= 31.18 else 'south' if p.coordinates[0] < 31.17 else 'central'
        bands[band].append(p.id)
    sorted_latitudes = sorted(p.coordinates[0] for p in nodes)
    gap = max((b-a)*111.2 for a,b in zip(sorted_latitudes, sorted_latitudes[1:]))
    causes = Counter(r['failure_attribution'] for r in rows if r['failure_attribution'])
    values = dict(theme_failure_count=sum(r['route_status'] != 'success' for r in rows),
        insufficient_route_count=sum(not r['minimum_viable_passed'] for r in rows),
        composition_failure_count=sum(r['route_status'] == 'composition_failure' for r in rows),
        candidate_pool_sizes={r['case']: dict(before=len(r['candidate_pool_before_filtering']),
            after=len(r['candidate_pool_after_filtering']), relevant=len(r['relevant_candidate_pool'])) for r in rows},
        non_museum_route_success={r['case']: r['route_status'] == 'success' for r in rows if 'museum_visit' in r['avoid_tags']},
        parks_public_space_route_success={r['case']: r['route_status'] == 'success' for r in rows if r['case'] in ('B', 'G', 'H')},
        geographic_gap_indicators=dict(bands=bands, largest_latitude_gap_km=gap,
            basis='approximate representative points; not actual pedestrian connectivity; no geographic failure inferred from distribution alone'),
        failure_causes={'route_role_composition': causes['route_role_composition'],
            'quality_node_shortage': causes['insufficient_high_quality_poi_supply'],
            'scoring_or_budget_constraint': causes['scoring_or_budget_constraint']})
    diag = zone_expansion_diagnostic(values)
    supply_failures = values['failure_causes']['quality_node_shortage']
    diag['zone_expansion_recommended'] = bool(diag['zone_expansion_recommended'] and supply_failures >= 2)
    diag.update(candidate_pool_size_per_case=values['candidate_pool_sizes'],
        failure_causes=values['failure_causes'], missing_themes=['art-only non-museum anchor eligibility'],
        actual_blocker='pure art/no museums has sufficient supporting nodes but no relevant audited anchor',
        recommended_expansion_direction=None, missing_geographic_segment=None,
        recommendation='Do not expand zone to solve an audited-role composition conflict; independently review policy/theme semantics first.')
    return diag

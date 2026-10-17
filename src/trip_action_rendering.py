"""Deterministic, shared CLI presentation for restricted edits and opt-in trace."""
import json
from .llm_client import redact_diagnostic


def safe_trace(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.casefold() in ('api_key', 'authorization', 'system_prompt', 'environment', 'headers') else safe_trace(v) for k, v in value.items()}
    if isinstance(value, list):return [safe_trace(v) for v in value]
    return redact_diagnostic(value)


def render_nlu_trace(trace):
    fields = [('User text', 'user_text'), ('Raw provider proposal', 'raw_provider_proposals'), ('Parsed actions', 'parsed_actions'),
              ('Normalized actions', 'normalized_actions'), ('POI resolution', 'poi_resolution'), ('Semantic validation', 'semantic_validation'),
              ('Domain validation', 'domain_validation'), ('Mutation scope', 'mutation_scope'), ('Execution result', 'execution_result'),
              ('Route diff / warnings', None)]
    for i, (label, key) in enumerate(fields, 1):
        value = trace.get(key) if key else dict(diff=trace.get('route_diff'), warnings=trace.get('warnings'), failure_stage=trace.get('failure_stage'))
        print(f'[{i}] {label}:', json.dumps(safe_trace(value), ensure_ascii=False))
    if trace.get('conflict_diagnostics'):
        print('[11] Conflict diagnostics:', json.dumps(safe_trace(trace['conflict_diagnostics']), ensure_ascii=False))


def conflict_summary(diagnostics):
    limit = diagnostics['hard_limit_minutes'];minimum = diagnostics['minimum_feasible_minutes']
    reasons = []
    if 'compression_search_limit' in diagnostics['blocking_constraints']:
        headline = f'I could not finish checking compressions for the {limit:g}-minute limit.'
        reasons.append(f'The minimum estimate is about {minimum:.1f} minutes; feasibility was not fully searched. Please choose stops to remove.')
    elif 'explicit_requested_order' in diagnostics['blocking_constraints']:
        headline = f'The requested order exceeds the {limit:g}-minute hard limit.'
        reasons.append(f'The shortest plan after permitted removals would be about {minimum:.1f} minutes; reordering alone cannot remove stops.')
    else:
        headline = f"I can't fit the remaining route into {limit:g} minutes."
        reasons.append(f'The shortest feasible remaining plan is about {minimum:.1f} minutes.')
    labels = {'must_go': 'you marked it as a must-go', 'explicitly_added_this_turn': 'you explicitly added or replaced it this turn'}
    for stop in diagnostics['protected_stops']:
        reasons.append(f"{stop['name']} is being kept because " + ' and '.join(labels.get(r, r.replace('_', ' ')) for r in stop['protection_reasons']) + '.')
    if not diagnostics['protected_stops'] and 'nonempty_remaining_route' in diagnostics['blocking_constraints']:
        reasons.append('Even the shortest single remaining stop exceeds the limit; the current contract requires a nonempty continuation.')
    return dict(headline=headline, reasons=reasons)


def render_mutation(payload):
    print('Change:', payload['mutation_scope'])
    for key in ('removed_stops', 'added_stops', 'kept_stops', 'reordered_stops'):
        print(key.replace('_', ' ').capitalize() + ':', ', '.join(p['name'] for p in payload[key]) or 'none')
    print(f"Estimated duration: about {payload['estimated_minutes']:.0f} minutes | Target: {payload['target_minutes']:g} minutes")
    if payload.get('hard_limit_minutes') is not None:print(f"Explicit hard limit: {payload['hard_limit_minutes']:g} minutes")
    else:print('Time target is soft.')
    if payload['time_warning']:
        print(f"Warning: this may take about {payload['time_warning']['estimated_overrun_minutes']:.0f} minutes longer than the target.")


def public_result(result, *, trace_nlu=False):
    import copy
    result = copy.deepcopy(result)
    if not trace_nlu:
        result.pop('nlu_trace', None)
        if result.get('trip_turn_result'):result['trip_turn_result'].pop('nlu_trace', None)
    return result


def render_read_result(read):
    query, value = read['query_type'], read['value']
    if query == 'multiple_read_queries':
        for item in value:render_read_result(item)
    elif query in ('show_original_route', 'show_current_route'):
        route = value['route'] if query == 'show_current_route' else value
        print(query.replace('_', ' ').capitalize() + ':', ' → '.join(p['name_en'] for p in route['ordered_pois']))
    elif query == 'show_route_history':
        for version in value:print(version['version_id'], '|', version['reason'].replace('_', ' '), ':', ' → '.join(p['name_en'] for p in version['route_snapshot']['ordered_pois']))
    elif query == 'why_latest_replan':
        for reason in value.get('reasons', []):print(reason)
        for key in ('added_stops', 'removed_stops', 'kept_stops'):print(key.replace('_', ' '), ':', ', '.join(p['name'] for p in value.get(key, [])))
    elif query == 'show_progress':
        print('Visited:', value['visited_count'], '| skipped:', value['skipped_count'], '| remaining:', value['remaining_count'], '| minutes:', value['remaining_minutes'])
        if value['current_stop']:print('Current planned stop:', value['current_stop']['name'])

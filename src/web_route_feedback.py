"""Presentation DTO derived from authoritative snapshots; never writes TripState."""
from .route_mutation import RouteMutationService
from .trip_state import TripState


def change_summary(before, after, result, repository, request_text):
    old, new = TripState({k:v for k,v in before.items() if k!='change_history'}), TripState({k:v for k,v in after.items() if k!='change_history'})
    service = RouteMutationService(repository)
    old_stops = [s for s in old.get_remaining_stops() if s['poi_id'] not in new.visited_poi_ids]
    new_stops = new.get_remaining_stops()
    origin_trip = new if new.visited_poi_ids != old.visited_poi_ids else old
    payload = result.get('mutation_result') or {}
    interpreted=payload.get('interpreted_intent') or result.get('parsed_command') or {}
    requested=sum((a.get('requested_count') or 1) for a in interpreted.get('actions',[]) if a['action_type']=='ADD_MATCHING_STOPS' or (a['action_type']=='ADD_INTEREST' and a.get('request_matching_insert')))
    changed = before['state_revision'] != after['state_revision']
    clarification = bool(result.get('clarification'))
    status = ('NEEDS_CLARIFICATION' if clarification else payload.get('execution_status','APPLIED') if changed
              else 'NO_CHANGE' if result['status'] in ('no_change','cancelled','success_query') else 'FAILED')
    if changed and result['status'] not in ('success_mutated','success_replanned','success_core_action'):
        status='PARTIALLY_APPLIED'
    # Same origin and estimator on both sides; live distances remain in the route itself.
    before_metrics = service.remaining_metrics(origin_trip, old_stops, old.current_intent)
    after_metrics = service.remaining_metrics(origin_trip, new_stops, new.current_intent)
    return dict(request_text=request_text, interpreted_intent=payload.get('interpreted_intent') or result.get('parsed_command'),
                execution_status=status, reason_code=payload.get('reason_code') or result.get('error_code') or result['status'],
                previous_route_version_id=before['route_versions'][-1]['version_id'],
                current_route_version_id=after['route_versions'][-1]['version_id'],
                before_metrics=before_metrics, after_metrics=after_metrics, **service.diff(old_stops,new_stops),
                visit_mode_changes=[dict(poi_id=b['poi_id'],before=b['selected_visit_mode'],after=n['selected_visit_mode'])
                    for b in old_stops for n in new_stops if b['poi_id']==n['poi_id'] and b['selected_visit_mode']!=n['selected_visit_mode']],
                preserved_must_go_ids=[p for p in old.must_go_remaining if p in new.remaining_poi_ids],
                requested_count=payload.get('requested_count') or requested or None,actual_added_count=len(set(new.remaining_poi_ids)-set(old.remaining_poi_ids)),
                warnings=[payload['time_warning']] if payload.get('time_warning') else [],
                explanation=(result.get('user_facing_summary') or {}).get('headline',''),
                preference_only=changed and service.ids(old_stops)==service.ids(new_stops) and before_metrics==after_metrics)

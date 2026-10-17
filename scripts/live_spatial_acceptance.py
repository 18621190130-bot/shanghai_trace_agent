"""Opt-in provider walking acceptance with independent spatial anchors."""
import json
import os
from pathlib import Path
from src import POIRepository, RouteRequest, Location
from src.poi_mapping import PoiMappingRepository
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.services.world_context_service import WorldContextService
from src.intent_models import RouteIntent, RouteMode
from src.trip_store import InMemoryTripStore, TripService
from src.trip_state import TripStateDelta
from src.trip_replanning import ReplanningCoordinator


def run_acceptance(output=None):
    if os.environ.get('RUN_LIVE_AMAP_TESTS') != '1' or not os.environ.get('AMAP_WEB_SERVICE_KEY'):
        raise RuntimeError('Live opt-in and key required')
    repo = POIRepository(); walking = WalkingRouteService.from_environment()
    world = WorldContextService.from_environment(repository=repo); rows = []
    for pid in ('p10', 'p12', 'p34', 'p35', 'pz_b72e3b8998b3'):
        poi = repo.get_poi_by_id(pid); anchor = poi.coordinates
        request = RouteRequest(180, preferred_zone=poi.zone_id, must_go_poi_ids=[pid], interest_tags=['history', 'architecture'])
        plan = WalkingRoutePlanner(repo, walking_service=walking).generate_route(request)
        assert plan.status == 'success' and plan.walking_data_status == 'AVAILABLE'
        assert plan.route_geometry and plan.walking_distance_m > 0
        stop = next(s for s in plan.ordered_pois if s.poi_id == pid)
        assert tuple(stop.estimated_coordinates) == anchor
        endpoints = [(leg[side]['lat'], leg[side]['lng']) for leg in plan.walking_legs for side in ('origin', 'destination')]
        assert anchor in endpoints
        assert world.check_arrival(Location(*anchor, 'GCJ02'), pid).status == 'ARRIVED'
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone=poi.zone_id, must_go_poi_ids=[pid], interest_tags=['history', 'architecture'])
        store = InMemoryTripStore(); core = TripService(store)
        trip = core.create_trip(plan, intent); core.start_trip(trip.trip_id); before = store.get(trip.trip_id)
        result = ReplanningCoordinator(store, repo, walking_service=walking).replan(trip.trip_id, TripStateDelta(request_replan=True, remaining_minutes=160))
        assert result.committed, result.to_dict()
        after = store.get(trip.trip_id)
        assert after.original_route == before.original_route and after.route_versions[0] == before.route_versions[0]
        assert after.active_route['walking_data_status'] == 'AVAILABLE'
        active = next(s for s in after.active_route['ordered_pois'] if s['poi_id'] == pid)
        assert tuple(active['estimated_coordinates']) == anchor
        rows.append(dict(core_id=pid, anchor=list(anchor), identity_mapping_status=PoiMappingRepository().get(pid)['identity_mapping_status'], route=plan.to_dict(), active_route=after.active_route, replan_result=result.to_dict(), original_version_unchanged=True, proximity='ARRIVED'))
    result = dict(phase='3B_2.2', source='live_amap', routes=rows, core_count=58)
    if output: Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    result = run_acceptance('examples/spatial_identity/live_acceptance.json')
    print(json.dumps([dict(core_id=r['core_id'], distance_m=r['route']['walking_distance_m'], geometry_points=len(r['route']['route_geometry']), replan=r['replan_result']['status']) for r in result['routes']], ensure_ascii=False, indent=2))

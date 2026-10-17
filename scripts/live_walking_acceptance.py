"""Opt-in real West Bund walking acceptance. No key or raw URL is emitted."""
import json
import os
from pathlib import Path

from src import POIRepository, RouteRequest
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.walking_models import Location


def run_acceptance(output=None):
    if os.environ.get('RUN_LIVE_AMAP_TESTS') != '1':
        raise RuntimeError('Set RUN_LIVE_AMAP_TESTS=1 for explicit live acceptance')
    if not os.environ.get('AMAP_WEB_SERVICE_KEY', '').strip():
        raise RuntimeError('AMAP_WEB_SERVICE_KEY is required')
    service = WalkingRouteService.from_environment()
    route = WalkingRoutePlanner(POIRepository(), walking_service=service).generate_route(
        RouteRequest(180, preferred_zone='west_bund'))
    start, end = route.ordered_pois[:2]
    single = service.get_walking_route(Location(*start.estimated_coordinates, start.coordinate_system),
                                      Location(*end.estimated_coordinates, end.coordinate_system))
    if not (single.distance_m > 0 and single.duration_s > 0 and single.steps and single.polyline):
        raise RuntimeError('Single-leg live acceptance failed')
    if route.walking_data_status != 'AVAILABLE':
        raise RuntimeError('West Bund live acceptance used fallback; inspect safe leg error codes')
    data = dict(source='live_amap_web_service', single_leg=as_single(single),
                stops=[dict(poi_id=s.poi_id, name=s.name_en, name_zh=s.name_zh) for s in route.ordered_pois],
                planning_distance_m=route.planning_distance_m, planning_walking_duration_min=route.planning_duration_min,
                real_walking_distance_m=route.walking_distance_m, real_walking_duration_s=route.walking_duration_s,
                leg_count=len(route.walking_legs), geometry_point_count=len(route.route_geometry),
                walking=route.walking)
    if output:
        path = Path(output);path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def as_single(result):
    return dict(distance_m=result.distance_m, duration_s=result.duration_s,
                step_count=len(result.steps), geometry_point_count=len(result.polyline),
                provider=result.provider, fetched_at=result.fetched_at)


if __name__ == '__main__':
    data = run_acceptance('examples/walking_routing/live_west_bund.json')
    print(json.dumps({k: v for k, v in data.items() if k != 'walking'}, ensure_ascii=False, indent=2))

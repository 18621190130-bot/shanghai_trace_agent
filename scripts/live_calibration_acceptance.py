"""Opt-in live acceptance of corrected coordinates, geometry and committed replans."""
import json
import os
from pathlib import Path
from src import POIRepository,RouteRequest,Location
from src.intent_models import RouteIntent,RouteMode
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.services.world_context_service import WorldContextService
from src.trip_store import InMemoryTripStore,TripService
from src.trip_state import TripState,TripStateDelta
from src.trip_replanning import ReplanningCoordinator


def run_acceptance(output=None):
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1' or not os.environ.get('AMAP_WEB_SERVICE_KEY'):raise RuntimeError('Live opt-in and key required')
    repo=POIRepository();walking=WalkingRouteService.from_environment();world=WorldContextService.from_environment(repository=repo);rows=[]
    for pid,zone in (('p4','hongkou_literary'),('p11','wukang_fuxing_xujiahui')):
        info=world.get_poi_live_info(pid);poi=repo.get_poi_by_id(pid)
        assert info.identity_mapping_status=='MATCHED' and info.location is not None and tuple(poi.coordinates)==(info.location.lat,info.location.lng)
        assert world.check_arrival(info.location,pid).status=='ARRIVED'
        request=RouteRequest(180,preferred_zone=zone,must_go_poi_ids=[pid],interest_tags=['history','architecture'])
        plan=WalkingRoutePlanner(repo,walking_service=walking).generate_route(request)
        assert plan.status=='success' and plan.walking_data_status=='AVAILABLE' and plan.route_geometry and plan.walking_distance_m>0
        stop=next(s for s in plan.ordered_pois if s.poi_id==pid);assert tuple(stop.estimated_coordinates)==poi.coordinates
        intent=RouteIntent(RouteMode.PLAN_FOR_ME,available_minutes=180,preferred_zone=zone,must_go_poi_ids=[pid],interest_tags=['history','architecture'])
        store=InMemoryTripStore();core=TripService(store);trip=core.create_trip(plan,intent);core.start_trip(trip.trip_id);before=store.get(trip.trip_id)
        result=ReplanningCoordinator(store,repo,walking_service=walking).replan(trip.trip_id,TripStateDelta(request_replan=True,remaining_minutes=160))
        assert result.committed,result.to_dict();after=store.get(trip.trip_id)
        assert before.route_versions[0]==after.route_versions[0] and before.original_route==after.original_route
        assert after.active_route['walking_data_status']=='AVAILABLE' and after.active_route['route_geometry']
        active=next(s for s in after.active_route['ordered_pois'] if s['poi_id']==pid);assert tuple(active['estimated_coordinates'])==poi.coordinates
        assert TripState.from_dict(after.to_dict()).to_dict()==after.to_dict()
        rows.append(dict(core_id=pid,live_info=info.to_dict(),corrected_coordinates=list(poi.coordinates),route=plan.to_dict(),replan_result=result.to_dict(),active_route=after.active_route,original_version_unchanged=True,proximity='ARRIVED'))
    p24=world.get_poi_live_info('p24');assert p24.provider_id=='B0MGOCVX94' and p24.live_data_status!='UNAVAILABLE'
    p7=world.get_poi_live_info('p7');assert p7.identity_mapping_status=='MATCHED' and p7.open_status=='NOT_APPLICABLE'
    result=dict(source='live_amap',coordinate_routes=rows,p24=p24.to_dict(),p7=p7.to_dict(),core_count=len(repo.get_all_pois()))
    if output:Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    value=run_acceptance('examples/location_awareness/calibration/live_acceptance.json')
    print(json.dumps(dict(core_count=value['core_count'],coordinate_routes=[dict(core_id=r['core_id'],walking_distance_m=r['route']['walking_distance_m'],walking_duration_s=r['route']['walking_duration_s'],geometry_points=len(r['route']['route_geometry']),replan_status=r['replan_result']['status']) for r in value['coordinate_routes']],p24_id=value['p24']['provider_id'],p7_open_status=value['p7']['open_status']),ensure_ascii=False,indent=2))

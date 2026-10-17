"""Prune a deleted stop from the current walking example without adding replacements."""
import json
import os
from pathlib import Path
from src import POIRepository
from src.geo_utils import haversine_km
from src.services.walking_route_service import WalkingRouteService
from scripts.calibrate_core_data import load,write,ROOT,OUT

def main():
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1':raise RuntimeError('Opt-in required to regenerate real geometry')
    baseline=load(OUT/'calibration/live_west_bund_before.json')
    path=ROOT/'examples/walking_routing/live_west_bund.json'
    if path.exists():
        current=load(path)
        if len(current['stops'])==5 and all(s['poi_id']!='p40' for s in current['stops']):write(OUT/'calibration/new_generated_west_bund.json',current)
    repo=POIRepository();stops=[s for s in baseline['stops'] if s['poi_id']!='p40']
    ordered=[];previous=None;distance=0;minutes=0
    factor=repo.defaults['walking_distance_factor'];speed=repo.defaults['walking_speed_m_per_min']
    for s in stops:
        poi=repo.get_poi_by_id(s['poi_id']);leg=haversine_km(previous,poi.coordinates)*factor if previous else 0
        duration=leg*1000/speed;distance+=leg*1000;minutes+=duration
        ordered.append(dict(poi_id=poi.id,name_en=poi.name_en,estimated_coordinates=list(poi.coordinates),coordinate_system='GCJ02',estimated_distance_from_previous_stop_km=leg,estimated_walking_minutes=duration))
        previous=poi.coordinates
    hydrated=WalkingRouteService.from_environment().hydrate_dict(dict(ordered_pois=ordered,request={},total_estimated_distance_km=distance/1000,total_estimated_walking_minutes=minutes))
    assert hydrated['walking_data_status']=='AVAILABLE' and hydrated['route_geometry']
    walking=hydrated['walking'];first=walking['legs'][0]
    result=dict(source='live_amap_web_service_after_authorized_stop_deletion',stops=stops,planning_distance_m=distance,planning_walking_duration_min=minutes,real_walking_distance_m=walking['total_distance_m'],real_walking_duration_s=walking['total_duration_s'],leg_count=len(walking['legs']),geometry_point_count=len(walking['geometry']),walking=walking,single_leg=dict(distance_m=first['distance_m'],duration_s=first['duration_s'],step_count=len(first['steps']),geometry_point_count=len(first['polyline']),provider='amap',fetched_at=first['fetched_at']),revision_note='Removed p40 only; retained the remaining stop sequence; no replacement was added.')
    write(path,result)
    deletion=load(ROOT/'data/deleted_core_pois.json');entry=deletion['deleted'][0]
    entry['affected_routes']=[dict(path=path.relative_to(ROOT).as_posix(),before=[s['poi_id'] for s in baseline['stops']],after=[s['poi_id'] for s in stops],replacement_ids=[],geometry_regenerated=True)]
    route_ref='examples/walking_routing/live_west_bund.json: stops/p40 and adjacent walking legs'
    if route_ref not in entry['removed_references']:entry['removed_references'].append(route_ref)
    entry['historical_evidence_preserved']=['examples/location_awareness/calibration/live_west_bund_before.json','Phase 2.5 pipeline candidates and frozen reports']
    write(ROOT/'data/deleted_core_pois.json',deletion)
    print(json.dumps(dict(stops=[s['poi_id'] for s in stops],walking_distance_m=walking['total_distance_m'],geometry_points=len(walking['geometry']),replacement_ids=[])))

if __name__=='__main__':main()

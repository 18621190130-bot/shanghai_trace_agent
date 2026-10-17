"""Opt-in read-only Phase 3B_2 acceptance, including Trip immutability."""
import json
import os
from pathlib import Path
from src import POIRepository,Location
from src.services.world_context_service import WorldContextService
from src.trip_state import TripState
from tools.demos.trip_demo import load_fixture


def run_acceptance(output=None):
    if os.environ.get('RUN_LIVE_AMAP_TESTS') != '1' or not os.environ.get('AMAP_WEB_SERVICE_KEY','').strip():
        raise RuntimeError('Live location acceptance requires RUN_LIVE_AMAP_TESTS=1 and AMAP_WEB_SERVICE_KEY')
    repo = POIRepository();world = WorldContextService.from_environment(repository=repo)
    plan,intent = load_fixture();trip = TripState.create(plan,intent);before = trip.to_dict()
    target = repo.get_poi_by_id('p28')
    gcj = Location(*target.coordinates,'GCJ02')
    gps = Location(31.16,121.46,'WGS84')
    resolved = world.reverse_geocode(gcj);gps_result = world.reverse_geocode(gps)
    if not all(r.live_data_status != 'UNAVAILABLE' and r.city=='上海市' and r.district and r.adcode and r.formatted_address for r in (resolved,gps_result)):
        raise RuntimeError('Live reverse geocoding did not meet acceptance')
    if gps_result.location.coordinate_system != 'GCJ02':raise RuntimeError('GPS coordinate not normalized')
    pois = [world.get_poi_live_info(pid) for pid in ('p28','p30','p34')]
    if any(p.live_data_status=='UNAVAILABLE' for p in pois[:2]):raise RuntimeError('Mapped museum/commercial info unavailable')
    if pois[2].live_info_applicability != 'NOT_APPLICABLE' or pois[2].open_status != 'NOT_APPLICABLE':raise RuntimeError('Street applicability invalid')
    if not any(p.opentime_today or p.opentime_week for p in pois[:2]):raise RuntimeError('No real opening-hours field returned')
    arrivals = []
    for meters in (30,120,1000):
        current = Location(gcj.lat+meters/111195.0802335,gcj.lng,'GCJ02')
        result = world.check_arrival(current,'p28');arrivals.append(result.to_dict())
    if [a['status'] for a in arrivals] != ['ARRIVED','NEAR','FAR']:raise RuntimeError('Arrival thresholds failed')
    if trip.to_dict()!=before:raise RuntimeError('World query mutated Trip')
    result = dict(source='live_amap_web_service',location=resolved.to_dict(),gps_location=gps_result.to_dict(),
                  pois=[p.to_dict() for p in pois],proximity=arrivals,trip_unchanged=True)
    if output:
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    data=run_acceptance('examples/location_awareness/live_acceptance.json')
    print(json.dumps(data,ensure_ascii=False,indent=2))

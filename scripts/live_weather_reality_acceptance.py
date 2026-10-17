"""One final A/B/C live run. Volatile weather/open-state values are observations."""
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from src import POIRepository, Location
from src.providers.amap import AmapClient, AmapWalkingProvider
from src.services.world_context_service import WorldContextService
from src.services.walking_route_service import WalkingRouteService
from src.route_entry import RouteEntryService
from src.intent_models import RouteIntent, RouteMode
from src.trip_state import TripState
from src.trip_store import InMemoryTripStore
from src.weather_models import local_time

OUTPUT = Path(__file__).resolve().parents[1] / 'examples/weather_reality/live_acceptance.json'


class AuditedClient(AmapClient):
    def __init__(self):
        super().__init__()
        self.calls = []

    def get(self, path, parameters):
        # Caller parameters contain no transport credential or raw URL.
        self.calls.append(dict(path=path, parameters=parameters))
        return super().get(path, parameters)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def valid_time(value):
    assert isinstance(value, str)
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None and parsed.utcoffset() is not None


def run_acceptance(output=OUTPUT):
    if os.environ.get('RUN_LIVE_AMAP_TESTS') != '1' or not os.environ.get('AMAP_WEB_SERVICE_KEY', '').strip():
        raise RuntimeError('Live opt-in and key required')
    client = AuditedClient(); repo = POIRepository()
    world = WorldContextService.from_environment(repository=repo, client=client)
    core_before = repo.get_raw_data()
    coordinates = {p.id:p.coordinates for p in repo.get_all_pois()}
    protected = [Path('data')/name for name in ('pois.json','core_spatial_profiles.json','amap_poi_mappings.json')]
    hashes = {p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    cases = []
    gps = Location(31.16,121.46,'WGS84')
    current = world.get_current_weather(gps)
    forecast = world.get_weather_forecast(gps)
    assert current.data_status == 'AVAILABLE', current.error_code
    assert forecast.data_status == 'AVAILABLE', forecast.error_code
    assert current.resolved_location['live_data_status'] == 'AVAILABLE'
    assert current.resolved_location['adcode'] and current.adcode and forecast.adcode
    assert current.resolved_location['location']['coordinate_system'] == 'GCJ02'
    assert forecast.precision == 'DAILY' and forecast.days
    assert current.temperature_c is not None and current.weather_text
    valid_time(current.report_time); valid_time(current.fetched_at)
    valid_time(forecast.report_time); valid_time(forecast.fetched_at)
    for day in forecast.days:
        assert day.date and day.day_weather and day.night_weather
    cases.append(dict(case='A_CURRENT_WEATHER',input=asdict(gps),current_weather=current.to_dict(),forecast=forecast.to_dict()))

    # Generating/hydrating is acceptance setup, outside the read-only check.
    walking = WalkingRouteService(AmapWalkingProvider(client))
    entry = RouteEntryService(repo, walking_service=walking)
    intent = RouteIntent(RouteMode.PLACES_IN_MIND, available_minutes=240,
                         must_go_poi_ids=['p28','p5'], preferred_zone='west_bund')
    generated = entry.generate(intent)
    assert generated.status == 'success', generated.errors
    plan = generated.route_plan
    assert plan.walking_data_status == 'AVAILABLE' and plan.walking_legs and plan.route_geometry
    trip = TripState.create(plan, generated.intent); trip.start_trip()
    store = InMemoryTripStore(); store.create(trip)
    before = trip.to_dict(); version = trip.route_versions[-1]
    snapshot_hash = digest([before, version])
    calls_before = len(client.calls)
    checked = world.check_route_reality(trip, version, now=local_time())
    check_calls = client.calls[calls_before:]
    assert not any(c['path'].startswith('/v3/direction') for c in check_calls)
    assert checked.data_quality['walking'] == 'AVAILABLE'
    assert checked.weather['data_status'] == 'AVAILABLE'
    assert any(v['applicability'] in ('FULL','LIMITED') and v['data_status'] in ('AVAILABLE','PARTIAL')
               for v in checked.data_quality['poi_live_info'].values())
    assert all(v['data_status'] != 'UNAVAILABLE' for v in checked.data_quality['poi_live_info'].values())
    valid_time(checked.checked_at)
    for stop in checked.metrics['stops']:
        valid_time(stop['estimated_arrival']); valid_time(stop['estimated_departure'])
    assert trip.to_dict() == before and store.get(trip.trip_id).to_dict() == before
    assert digest([trip.to_dict(), trip.route_versions[-1]]) == snapshot_hash
    calls_before_repeat = len(client.calls)
    world.check_route_reality(trip, version, now=local_time())
    assert len(client.calls) == calls_before_repeat
    assert trip.to_dict() == before
    cases.append(dict(case='B_EXISTING_REAL_ROUTE',route_poi_ids=[s.poi_id for s in plan.ordered_pois],
                      walking_status=plan.walking_data_status,geometry_point_count=len(plan.route_geometry),
                      walking_distance_m=plan.walking_distance_m,walking_duration_s=plan.walking_duration_s,
                      route_version=version,result=checked.to_dict(),requests_during_check=check_calls,
                      cached_repeat_caused_requests=0,trip_snapshot_sha256=snapshot_hash))

    area_intent = RouteIntent(RouteMode.PLACES_IN_MIND,available_minutes=120,must_go_poi_ids=['p35'])
    area_generated = entry.generate(area_intent)
    assert area_generated.status == 'success', area_generated.errors
    area = TripState.create(area_generated.route_plan, area_generated.intent); area.start_trip()
    area_before = area.to_dict()
    area_checked = world.check_route_reality(area, area.route_versions[-1], now=local_time())
    assert not any(w.code in ('OPENING_HOURS_UNKNOWN','POI_CLOSED') and w.poi_id == 'p35' for w in area_checked.warnings)
    assert area_checked.data_quality['poi_live_info']['p35']['applicability'] == 'NOT_APPLICABLE'
    assert area.to_dict() == area_before
    cases.append(dict(case='C_NOT_APPLICABLE_AREA',poi_id='p35',result=area_checked.to_dict()))
    assert repo.get_raw_data() == core_before
    assert {p.id:p.coordinates for p in repo.get_all_pois()} == coordinates and len(coordinates) == 58
    assert hashes == {p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    result = dict(phase='3B_4',source='live_amap',checked_at=local_time().isoformat(),cases=cases,
                  provider_calls=client.calls,trip_state_unchanged=True,route_versions_unchanged=True,
                  route_history_unchanged=True,core_repository_unchanged=True,core_count=58,
                  protected_data_sha256=hashes,walking_requests_during_reality_check=0)
    if output:
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    result = run_acceptance()
    print(json.dumps(dict(cases=[c['case'] for c in result['cases']],request_count=len(result['provider_calls']),
                          trip_state_unchanged=result['trip_state_unchanged']),ensure_ascii=False,indent=2))

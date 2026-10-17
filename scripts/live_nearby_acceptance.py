"""Final acceptance only: 3 seven-category cases, 12 grouped around calls, no detail requests."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from src import POIRepository, Location
from src.providers.amap import AmapClient
from src.services.world_context_service import WorldContextService
from src.poi_mapping import PoiMappingRepository
from src.trip_state import TripState
from src.trip_store import InMemoryTripStore
from tools.demos.trip_demo import load_fixture

OUTPUT=Path(__file__).resolve().parents[1]/'examples/nearby_rest_stops/live_acceptance.json'


class AuditedClient(AmapClient):
    def __init__(self):
        super().__init__(); self.calls=[]; self.observations=[]

    def get(self,path,parameters):
        self.calls.append(dict(path=path,parameters=parameters))  # Only caller parameters, never transport URL/key.
        data=super().get(path,parameters)
        if path=='/v5/place/around':
            allowed=('id','name','location','distance','type','typecode','address','tel','opentime_today','opentime_week')
            business=('tel','rating','cost','opentime_today','opentime_week','tag','keytag','rectag')
            def sanitize(value):
                if isinstance(value,str):return self.redact_text(value)
                if isinstance(value,list):return [sanitize(v) for v in value]
                if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items()}
                return value
            rows=[]
            for raw in data.get('pois',[]):
                if not isinstance(raw,dict):continue
                row={k:raw.get(k) for k in allowed};b=raw.get('business')
                row['business']={k:b.get(k) for k in business} if isinstance(b,dict) else None
                rows.append(sanitize(row))
            self.observations.append(dict(request_index=len(self.calls)-1,pois=rows))
        return data


def run_acceptance(output=OUTPUT):
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1' or not os.environ.get('AMAP_WEB_SERVICE_KEY','').strip():
        raise RuntimeError('Live opt-in and key required')
    repo=POIRepository();client=AuditedClient();world=WorldContextService.from_environment(repository=repo,client=client)
    plan,intent=load_fixture();trip=TripState.create(plan,intent);trip.start_trip();store=InMemoryTripStore();store.create(trip)
    before=store.get(trip.trip_id).to_dict();kb=repo.get_raw_data();coordinates={p.id:p.coordinates for p in repo.get_all_pois()}
    protected=[Path('data')/name for name in ('pois.json','core_spatial_profiles.json','amap_poi_mappings.json')]
    hashes={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    cases=[]
    for name,arguments in (('A_CURRENT_GPS',dict(location=Location(31.16,121.46,'WGS84'))),
                           ('B_P28_WEST_BUND',dict(core_poi_id='p28')),
                           ('C_P35_XUJIAHUI',dict(core_poi_id='p35'))):
        result=world.search_nearby_services(**arguments)
        assert result.status=='AVAILABLE',result.to_dict()['errors']
        assert result.origin.coordinate_system=='GCJ02' and result.radius_m==800
        assert len(result.requested_categories)==7
        assert len({p.service_poi_id for p in result.results})==len(result.results)
        assert all(0<=p.distance_m<=800 for p in result.results)
        assert all(p.location.coordinate_system=='GCJ02' and p.service_poi_id.startswith('amap:') for p in result.results)
        assert all(count<=5 for count in result.to_dict()['category_counts'].values())
        if arguments.get('core_poi_id'):
            poi=repo.get_poi_by_id(arguments['core_poi_id']);assert (result.origin.lat,result.origin.lng)==poi.coordinates
        if name=='C_P35_XUJIAHUI':
            assert PoiMappingRepository().get('p35')['identity_mapping_status']=='NOT_FOUND'
            a=repo.get_spatial_profile('p35')['route_anchor'];assert (result.origin.lat,result.origin.lng)==(a['lat'],a['lng'])
        cases.append(dict(case=name,input={k:asdict(v) if isinstance(v,Location) else v for k,v in arguments.items()},result=result.to_dict()))
    assert store.get(trip.trip_id).to_dict()==before and repo.get_raw_data()==kb
    assert {p.id:p.coordinates for p in repo.get_all_pois()}==coordinates and len(coordinates)==58
    assert hashes=={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    calls_before_cache=len(client.calls);world.search_nearby_services(core_poi_id='p35')
    assert len(client.calls)==calls_before_cache
    paths=[r['path'] for r in client.calls]
    assert paths.count('/v5/place/around')==12 and paths.count('/v3/assistant/coordinate/convert')==1
    assert all(p in ('/v5/place/around','/v3/assistant/coordinate/convert') for p in paths)
    result=dict(phase='3B_3',source='live_amap',cases=cases,provider_calls=client.calls,provider_observations=client.observations,
        around_request_count=12,detail_request_count=0,official_coordinate_conversion_count=1,
        cached_repeat_caused_requests=0,trip_unchanged=True,route_versions_unchanged=True,
        core_repository_unchanged=True,protected_data_sha256=hashes,core_count=58,
        p35_identity_mapping_status='NOT_FOUND')
    if output:Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    result=run_acceptance()
    print(json.dumps([dict(case=c['case'],status=c['result']['status'],origin=c['result']['origin'],counts=c['result']['category_counts']) for c in result['cases']],ensure_ascii=False,indent=2))

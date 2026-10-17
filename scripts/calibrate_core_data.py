"""Idempotent, explicitly human-authorized Core corrections for Phase 3B_2.1."""
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from src import POIRepository
from src.geo_utils import haversine_km
from src.providers.amap import AmapClient
from src.providers.amap.world import AmapPoiProvider
from src.world_models import utc_now

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'examples/location_awareness'

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temp,path)

def remove_references(value, path='', removed=None):
    removed = removed if removed is not None else []
    if isinstance(value,list):
        out=[]
        for i,item in enumerate(value):
            if item=='p40' or isinstance(item,dict) and (item.get('poi_id')=='p40' or item.get('id')=='p40'):
                removed.append(path+'/'+str(i));continue
            out.append(remove_references(item,path+'/'+str(i),removed))
        return out
    if isinstance(value,dict):
        out={}
        for key,item in value.items():
            if key=='p40' or item=='p40':removed.append(path+'/'+key);continue
            out[key]=remove_references(item,path+'/'+key,removed)
        return out
    return value

def main():
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1':raise RuntimeError('Explicit live calibration opt-in required')
    production = ROOT/'data/pois.json'
    raw = load(production);before = copy.deepcopy(raw)
    baseline = load(OUT/'calibration/pois_before.json')
    provider = AmapPoiProvider(AmapClient())
    corrections=[];details={}
    existing_path=OUT/'coordinate_corrections.json'
    existing={r['core_id']:r for r in load(existing_path)['corrections']} if existing_path.exists() else {}
    for pid,amap_id in (('p4','B0015474E7'),('p11','B00156O2YR')):
        poi=next(p for p in raw['pois'] if p['id']==pid)
        info=provider.get_poi_detail(amap_id)
        if info.location is None or info.location.coordinate_system!='GCJ02':raise RuntimeError('Formal GCJ02 coordinate unavailable')
        if info.name != poi['name']['zh']:raise RuntimeError('Confirmed provider name changed; correction aborted')
        details[pid]=info.to_dict()
        old=next(p for p in baseline['pois'] if p['id']==pid)['location']
        latkey,lngkey=('representative_lat','representative_lng') if poi['poi_type']=='district' else ('lat','lng')
        oldpoint=(old[latkey],old[lngkey]);newpoint=(info.location.lat,info.location.lng)
        if pid in existing and existing[pid]['new_coordinate']!=asdict(info.location):raise RuntimeError('Provider coordinate changed after recorded calibration')
        poi['location'][latkey],poi['location'][lngkey]=newpoint
        # Only the authorized coordinate pair is changed. Cultural knowledge and provenance remain intact.
        corrections.append(existing.get(pid) or dict(core_id=pid,name=poi['name']['zh'],old_coordinate=dict(lat=oldpoint[0],lng=oldpoint[1],coordinate_system=old['coordinate_system']),new_coordinate=asdict(info.location),amap_poi_id=amap_id,old_to_new_distance_m=haversine_km(oldpoint,newpoint)*1000,reason='Project owner confirmed same-name same-district provider parent as the more reliable real-world coordinate.',reviewed=True,fetched_at=info.fetched_at))
    removed=[]
    raw=remove_references(raw,removed=removed)
    for i,p in enumerate(raw['pois'],1):p['display_order']=i
    raw['metadata']['poi_count']=len(raw['pois'])
    for z in raw['metadata']['walk_zones']:z['poi_count']=sum(p['walk_zone']['id']==z['id'] for p in raw['pois'])
    assert len(raw['pois'])==58
    write(production,raw);POIRepository(production)
    write(existing_path,dict(corrections=corrections))
    write(OUT/'calibration/coordinate_provider_details.json',details)
    deletion_path=ROOT/'data/deleted_core_pois.json'
    if not deletion_path.exists():
        write(deletion_path,dict(deleted=[dict(core_id='p40',name='上海摄影艺术中心',reason='Project owner confirmed erroneous / false Core POI in Phase 3B_2.1.',affected_routes=[],removed_references=removed,active_route_inventory=['tools.demos.trip_demo.DEFAULT_FIXTURE: no p40; preserved unchanged','RouteEngine/entry/replan: generated from current production repository; p40 no longer selectable'],historical_evidence_preserved=['examples/walking_routing/live_west_bund.json','Phase 2.5 pipeline candidates and regression reports'],reviewed=True,deleted_at=utc_now())]))
    write(OUT/'calibration/core_revision_manifest.json',dict(phase='3B_2.1',before_sha256=hashlib.sha256((OUT/'calibration/pois_before.json').read_bytes()).hexdigest(),after_sha256=hashlib.sha256(production.read_bytes()).hexdigest(),authorized_changes=['p40 deletion and related references','p4/p11 coordinate pair','continuous display numbering and counts'],core_count=58))
    print(json.dumps(dict(core_count=58,corrections=corrections,removed_references=removed),ensure_ascii=False,indent=2))

if __name__=='__main__':main()

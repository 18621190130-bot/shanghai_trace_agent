"""Authorized spatial identity corrections backed by saved formal provider evidence."""
import copy
from pathlib import Path
from src import POIRepository
from src.geo_utils import haversine_km
from scripts.calibrate_core_data import load,write,ROOT,OUT

SOURCES={
'p10':'https://www.shhk.gov.cn/xwzx/002003/20211201/f7e7613f-be5d-4c30-93c1-e2edbbf45b2d.html',
'p12':'https://lhsr.sh.gov.cn/ywdt/20240807/5c8cb815-ef70-4bd1-909d-b31c45574382.html',
'p34':'https://www.shanghai.gov.cn/xxzfgzwj/20220127/d2c2979752314dc69738454f24cd515c.html',
'p25':'https://www.shhk.gov.cn/xwzx/002005/20251222/2cbc6abf-6327-465e-859c-c1c29873c841.html',
'pz_b72e3b8998b3':'https://www.shhk.gov.cn/xwzx/002003/20240226/c159f769-0d8b-48d5-a8a9-d7fc432cfdad.html'}

def main():
    e=load(ROOT/'examples/spatial_identity/provider_evidence.json');raw=load(ROOT/'data/pois.json');repo=POIRepository()
    mapping=load(ROOT/'data/amap_poi_mappings.json');manual=load(ROOT/'data/amap_manual_confirmations.json')
    audit=load(OUT/'coordinate_corrections.json');ids={r['core_id'] for r in audit['corrections']}
    checks={'p10':('今潮8弄','虹口区','特色商业街','四川北路989弄'),
            'p12':('陕南邨','黄浦区','住宅小区','陕西南路187弄'),
            'p34':('南京路步行街','黄浦区','道路名','黄浦区'),
            'p25':('1927·鲁迅与内山纪念书局','虹口区','科教文化','四川北路2056号'),
            'pz_b72e3b8998b3':('多伦路文化名人街','虹口区','特色商业街','多伦路')}
    for pid,(name,district,ptype,address) in checks.items():
        item=e['details'][pid];r=item['raw'][0];info=item['normalized'];point=info['location']
        assert r['name']==name and r['adname']==district and ptype in r['type'] and address in r['address']
        assert point['coordinate_system']=='GCJ02' and e['surroundings'][pid]
        p=next(p for p in raw['pois'] if p['id']==pid);method='MANUAL_SEMANTIC_SCOPE_CONFIRMATION'
        reason='Owner confirmed current product semantic scope; official detail name, district, address and type reverified. Historic/road aliases remain cultural evidence, not the live identity.'
        if pid in ('p10','p12','p34'):
            method='MANUAL_COORDINATE_CORRECTION';reason='Owner authorized trustworthy same-entity provider location priority. Name, district, type, lane/street address, aliases, official public-place context and surrounding map entities verified; distance alone is not an identity veto.'
            location=p['location'];lat,lng=('representative_lat','representative_lng')
            old=copy.deepcopy(location);old_gcj=repo.get_poi_by_id(pid).coordinates
            if pid not in ids:
                audit['corrections'].append(dict(core_id=pid,name=name,old_coordinate=dict(lat=old[lat],lng=old[lng],coordinate_system=old['coordinate_system']),old_coordinate_gcj02=dict(lat=old_gcj[0],lng=old_gcj[1],coordinate_system='GCJ02'),new_coordinate=point,amap_poi_id=r['id'],old_to_new_distance_m=haversine_km(old_gcj,(point['lat'],point['lng']))*1000,reason=reason,reviewed=True,reviewed_by='CODEX_UNDER_OWNER_AUTHORIZATION',phase='3B_2.2',evidence_reference='examples/spatial_identity/provider_evidence.json',public_context_source=SOURCES[pid]))
            location[lat],location[lng]=point['lat'],point['lng']
            # p34 previously WGS84: changing its datum label is essential for truthful formal GCJ02 data.
            if pid=='p34':location['coordinate_system']='GCJ-02 / Amap formal identity coordinate (Phase 3B_2.2)'
        row=mapping[pid];row.update(identity_mapping_status='MATCHED',amap_poi_id=r['id'],matched_name=r['name'],confidence=1.0,reviewed=True,reviewed_by='CODEX_UNDER_OWNER_AUTHORIZATION',match_method=method,live_info_applicability='FULL' if pid=='p25' else 'NOT_APPLICABLE',distance_m=0 if pid in ('p10','p12','p34') else row.get('distance_m'),notes=reason,identity_evidence_reference='examples/spatial_identity/provider_evidence.json',public_context_source=SOURCES[pid])
        # District/open-space data does not acquire a fictitious unified business state.
        row['entity_type']={'p10':'historic_district','p12':'historic_district','p34':'street','p25':'cultural_bookshop','pz_b72e3b8998b3':'cultural_street'}[pid]
        manual[pid]={k:row[k] for k in ('amap_poi_id','matched_name','match_method','entity_type','live_info_applicability','aliases','reviewed','notes','reviewed_by','identity_evidence_reference','public_context_source')}
    write(ROOT/'data/pois.json',raw);write(ROOT/'data/amap_poi_mappings.json',mapping);write(ROOT/'data/amap_manual_confirmations.json',manual);write(OUT/'coordinate_corrections.json',audit)
    print('Verified/corrected p10 p12 p34; finalized current-bookshop and cultural-street identities. p35 remains independent NOT_FOUND.')
if __name__=='__main__':main()

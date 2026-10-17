"""Build first-version, explicitly curated/derived spatial profiles for all Core IDs."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from src import POIRepository,Location
from src.geo_utils import to_gcj02,haversine_km
from src.spatial_profiles import SpatialProfileRepository
from scripts.calibrate_core_data import ROOT,load,write

OUT=ROOT/'examples/spatial_identity'

def coord(lat,lng):return dict(lat=lat,lng=lng,coordinate_system='GCJ02')
def make_anchor(point,source,name,reason,confidence=.8,evidence=None):
    return dict(**point,source=source,confidence=confidence,name=name,notes=reason,evidence=evidence or [])
def main():
    evidence=load(OUT/'provider_evidence.json');mappings=load(ROOT/'data/amap_poi_mappings.json')
    # Build from canonical identity/representative coordinates, not an older sidecar overlay.
    current=load(ROOT/'data/pois.json')
    raw={p['id']:p for p in current['pois']};rows={}
    def find(query,fragment,ptype=None):
        candidates=[r for r in evidence['queries'][query] if fragment in r['name'] and (not ptype or ptype in (r['poi_type'] or ''))]
        if not candidates:raise ValueError('Required endpoint evidence missing: '+query)
        return candidates[0]
    def feature(query,fragment,reason,ptype=None):
        r=find(query,fragment,ptype)
        return make_anchor(r['location'],'AMAP_POI',r['name'],reason,.88,[dict(provider_id=r['provider_id'],query=query)])
    radii={'p7':130,'p9':150,'p10':150,'p11':160,'p12':160,'p15':240,'p16':420,'p23':180,'p30':350,'p14':100,'p37':160,'p42':100,'pz_0db17d82e9ec':300,'pz_a446052910a0':100,'pz_de47b0cf3e98':150,'p38':200,'p39':350,'pz_a74f9e58195a':160,'pz_0b545bb1cf2a':220,'pz_68957332b418':250,'pz_8919938b21f2':150,'pz_bd40d04c7f5d':300,'pz_553cfd36707c':120,'pz_a27dbbc6cab8':160,'pz_09b5938601ee':300,'p2':90}
    linear={'p34','pz_b72e3b8998b3','pz_b4acff8f32fc','pz_a87eb2b5b5da','pz_cc5300aee299'}
    areas={p['id'] for p in current['pois'] if p['poi_type'] in ('park','district','street')} - linear
    areas|={'p14','p37','p42'}
    for p in current['pois']:
        pid=p['id'];location=p['location'];area=p['poi_type'] in ('street','district')
        lat,lng=(location['representative_lat'],location['representative_lng']) if area else (location['lat'],location['lng'])
        gcj=to_gcj02(lat,lng,location['coordinate_system']);kind='LINEAR' if pid in linear else 'AREA' if pid in areas else 'POINT'
        anchor=make_anchor(coord(*gcj),'CORE_EXISTING',p['name']['zh']+' City Walk anchor','Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.',.75,[dict(identity_id=mappings[pid]['amap_poi_id'],identity_offset_m=mappings[pid].get('distance_m'),audit_reference='examples/spatial_identity/identity_audit.json')])
        row=dict(core_id=pid,spatial_type=kind,route_anchor=anchor,secondary_anchor=None,anchor_source=anchor['source'],spatial_extent=None,extent_source=None,extent_confidence=None,extent_status='NOT_REQUIRED' if kind=='POINT' else 'CURATED_APPROXIMATE',reviewed=False,notes='Identity, navigation anchor and extent are separate. No geofence/Trip automation. Spatial proposal is not owner-reviewed.',identity_coordinate=coord(*gcj))
        if kind=='AREA':
            radius=radii.get(pid,200)
            row['spatial_extent']=dict(type='CENTER_RADIUS',coordinate_system='GCJ02',center=coord(*gcj),radius_m=radius,extent_source='TRACEMATE_CURATED',extent_confidence=.55,notes=f'First-version City Walk experience vicinity: {radius}m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.',evidence=[dict(core_id=pid,core_type=p['poi_type'],address=location.get('address_zh'),identity_id=mappings[pid]['amap_poi_id'])])
        if pid=='p35':
            anchor=feature('肇嘉浜路与漕溪北路交叉口','肇嘉浜路与虹桥路交叉口','Public junction beside the central Metro City/Grand Gateway cluster; curated City Walk entry, not a mall identity or region centroid.','路口名')
            anchor['source']='TRACEMATE_CURATED';anchor['confidence']=.82
            row['route_anchor']=anchor
            row['spatial_extent']=dict(type='POLYGON',coordinate_system='GCJ02',vertices=[coord(31.1908,121.4358),coord(31.1908,121.4416),coord(31.1965,121.4416),coord(31.1965,121.4358),coord(31.1908,121.4358)],extent_source='TRACEMATE_CURATED',extent_confidence=.65,notes='Product review polygon limited to the Core central Metro City/Grand Gateway shopping and public-space cluster, including the adjacent cathedral frontage. Excludes the wider Xujiahui central activity district. Approximate bounds, not Amap or governmental commercial-district boundary.',evidence=[dict(provider_id=find('美罗城','美罗城')['provider_id'],location=find('美罗城','美罗城')['location']),dict(provider_id=find('港汇恒隆广场','港汇恒隆')['provider_id'],location=find('港汇恒隆广场','港汇恒隆')['location']),dict(public_context_source='https://sww.sh.gov.cn/swdt/20240220/42959b17d7da40d6b1ee2da5b196d64a.html')])
        if pid=='p14':
            detail=evidence['details']['p14'];official=detail['normalized']
            assert official['provider_id']=='B00155G6WO' and official['name']=='外滩-陈毅广场' and detail['raw'][0]['adname']=='黄浦区'
            row['route_anchor']=make_anchor(official['location'],'AMAP_POI',official['name'],'Verified formal square identity position takes priority over the older Core point 296.5m away. Public square visit anchor; no Core identity coordinate rewrite.',.9,[dict(provider_id='B00155G6WO',detail_reference='examples/spatial_identity/provider_evidence.json')])
            row['spatial_extent']['center']=official['location']
            row['spatial_extent']['notes']='100m first-version public square experience vicinity around the verified formal Chen Yi Square position. Not the entire Bund or a provider boundary.'
        if pid in linear:
            if pid=='p34':
                start=feature('南京路步行街西入口','南京东路观光车','Recommended western public walking-start vicinity beside the sightseeing-car position. No ticket/service use is required; not claimed as an official surveyed gate.')
                end=feature('南京东路与中山东一路交叉口','交叉口','Eastern walking-space exit towards the Bund.','路口名')
                vertices=[{k:start[k] for k in ('lat','lng','coordinate_system')},coord(31.235348,121.480432),find('南京路步行街西入口','南京东路与河南中路交叉口')['location'],{k:end[k] for k in ('lat','lng','coordinate_system')}]
                extent_type='POLYLINE';source='DERIVED';ref='https://www.shanghai.gov.cn/xxzfgzwj/20220127/d2c2979752314dc69738454f24cd515c.html'
            elif pid=='pz_b72e3b8998b3':
                start=feature('多伦路牌坊','文化名人街牌坊','Enter the cultural street at the southern archway; not its ordinary road identity.')
                end=feature('多伦路与四川北路交叉口','多伦路与四川北路交叉口','Northern connection back to Sichuan North Road.','路口名')
                vertices=[{k:start[k] for k in ('lat','lng','coordinate_system')},coord(31.2630,121.48185),coord(31.264124,121.481748),{k:end[k] for k in ('lat','lng','coordinate_system')}]
                extent_type='POLYLINE';source='TRACEMATE_CURATED';ref='https://www.shhk.gov.cn/xwzx/002003/20240226/c159f769-0d8b-48d5-a8a9-d7fc432cfdad.html'
            elif pid=='pz_b4acff8f32fc':
                start=feature('甜爱路与四川北路交叉口','交叉口','Southern entry from Sichuan North Road; start a walk along the cultural street.','路口名')
                end=feature('甜爱路与甜爱支路交叉口','交叉口','Secondary anchor at Tianai Branch Road; first-version romantic-walk segment.','路口名')
                vertices=None;extent_type='START_END';source='DERIVED';ref='https://www.shhk.gov.cn/xwzx/002005/20251222/2cbc6abf-6327-465e-859c-c1c29873c841.html'
            elif pid=='pz_a87eb2b5b5da':
                start=feature('武康路与淮海中路交叉口','交叉口','Recommended southern entry beside Wukang Mansion; walk north along the historical street.','路口名')
                end=feature('武康路与华山路交叉口','交叉口','Northern secondary anchor connecting Huashan Road.','路口名')
                vertices=None;extent_type='START_END';source='DERIVED';ref='https://mzj.sh.gov.cn/lnb-lyxx/20231220/92ff0d6b62494a3e92fbd357e060b120.html'
            else:
                start=feature('福州路与西藏中路交叉口','交叉口','Western entry for the bookish/street-scene walk.','路口名')
                end=feature('福州路与中山东一路交叉口','交叉口','Eastern secondary anchor at the Bund approach.','路口名')
                vertices=None;extent_type='START_END';source='DERIVED';ref=None
            row['route_anchor']=start;row['secondary_anchor']=end
            extent=dict(type=extent_type,coordinate_system='GCJ02',extent_source=source,extent_confidence=.7 if source=='DERIVED' else .6,notes='Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.',evidence=[*start['evidence'],*end['evidence'],dict(public_context_source=ref)])
            if vertices:extent['vertices']=vertices
            else:extent.update(start={k:start[k] for k in ('lat','lng','coordinate_system')},end={k:end[k] for k in ('lat','lng','coordinate_system')})
            row['spatial_extent']=extent
        row['anchor_source']=row['route_anchor']['source']
        if row['spatial_extent']:
            row['extent_source']=row['spatial_extent']['extent_source'];row['extent_confidence']=row['spatial_extent']['extent_confidence']
        rows[pid]=row
    SpatialProfileRepository(records=rows,core_ids=raw)
    write(ROOT/'data/core_spatial_profiles.json',rows)
    overrides=[]
    for pid,row in rows.items():
        identity=row['identity_coordinate'];a=row['route_anchor']
        if (identity['lat'],identity['lng'])==(a['lat'],a['lng']):continue
        overrides.append(dict(core_id=pid,name=raw[pid]['name']['zh'],change_kind='SPATIAL_ANCHOR_ONLY',
            core_identity_coordinate_preserved=True,identity_coordinate_gcj02=identity,route_anchor=a,
            offset_m=haversine_km((identity['lat'],identity['lng']),(a['lat'],a['lng']))*1000,
            notes='Navigation entry/public visit position independent of unchanged Core identity coordinate.'))
    write(OUT/'anchor_overrides.json',dict(overrides=overrides))
    counts=Counter(r['spatial_type'] for r in rows.values())
    write(OUT/'spatial_audit.json',dict(total=58,counts=dict(counts),area_linear_with_valid_anchor=sum(r['spatial_type']!='POINT' for r in rows.values()),area_linear_with_valid_extent=sum(r['spatial_type']!='POINT' and r['spatial_extent'] is not None for r in rows.values()),provider_boundaries=0,reviewed_spatial_profiles=0))
    print(dict(counts))
if __name__=='__main__':main()

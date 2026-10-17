"""Full Core identity calibration; no runtime Nearby Search product or Core writes."""
import argparse
from collections import Counter
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
import re
from src import POIRepository,Location
from src.geo_utils import haversine_km,to_gcj02
from src.poi_mapping import match_poi,PoiMappingRepository,DEFAULT_MAPPING_PATH
from src.providers.amap import AmapClient
from src.providers.amap.world import AmapPoiProvider
from src.providers.base import ExternalProviderError
from src.world_models import utc_now,MappingStatus,LiveInfoApplicability

MANUAL_PATH = DEFAULT_MAPPING_PATH.with_name('amap_manual_confirmations.json')
SPECIAL_ALIASES = {
 'p24':['中国共产党第一次全国代表大会纪念馆','中共一大纪念馆','一大纪念馆'],
 'p7':['新天地北里','新天地北里街区','Xintiandi North Block'],
}
EXTRA_ALIASES = {'p2':['嘉善路与永康路交叉口','永康路与嘉善路交叉口'],
                 'pz_a446052910a0':['山阴路274弄小区']}

def audit(repository,provider,*,existing=None,confirmations=None):
    raw={p['id']:p for p in repository.get_raw_data()['pois']}
    confirmations = confirmations if confirmations is not None else json.loads(MANUAL_PATH.read_text(encoding='utf-8'))
    existing = existing or {};mappings={}
    for poi in repository.get_all_pois():
        poi=replace(poi,coordinates=to_gcj02(*poi.original_coordinates,poi.original_coordinate_system))
        metadata=raw[poi.id]
        district=re.search('(徐汇区|黄浦区|虹口区|静安区)',metadata['location'].get('address_zh',''))
        expected=district.group() if district else {'wukang_fuxing_xujiahui':'徐汇区','old_city_central':'黄浦区','hongkou_literary':'虹口区','west_bund':'徐汇区'}.get(poi.zone_id)
        aliases=list(dict.fromkeys([*metadata['name'].get('aliases',()),*SPECIAL_ALIASES.get(poi.id,()),*EXTRA_ALIASES.get(poi.id,())]))
        queries=[];errors=[];candidates=[]
        manual = confirmations.get(poi.id)
        previous = existing.get(poi.id,{})
        if manual is None and poi.id=='p24' and previous.get('reviewed') and previous.get('identity_mapping_status')=='MATCHED':manual=previous
        row=match_poi(poi,[],aliases=aliases,expected_district=expected)
        if manual:
            row.update(manual)
            row.update(identity_mapping_status='MATCHED',confidence=1.0,aliases=list(dict.fromkeys([*aliases,*manual.get('aliases',())])))
            queries.append(dict(method='detail',id=manual['amap_poi_id']))
            try:
                detail=provider.get_poi_detail(manual['amap_poi_id'])
                if not isinstance(detail.name,str) or detail.location is None:raise ValueError('Invalid detail')
                row.update(provider_detail_name=detail.name,distance_m=haversine_km(poi.coordinates,(detail.location.lat,detail.location.lng))*1000,provider_location=asdict(detail.location))
            except Exception as exc:errors.append(exc.code if isinstance(exc,ExternalProviderError) else 'provider_response_invalid')
        else:
            names=list(dict.fromkeys(SPECIAL_ALIASES.get(poi.id,[]) or [poi.name_zh,*aliases]))
            for name in names:
                queries.append(dict(method='text',keywords=name))
                try:candidates.extend(provider.search_mapping_candidates(name))
                except Exception as exc:errors.append(exc.code if isinstance(exc,ExternalProviderError) else 'provider_response_invalid')
            row=match_poi(poi,candidates,aliases=aliases,expected_district=expected)
            if poi.id in SPECIAL_ALIASES or row['identity_mapping_status']!='MATCHED':
                # Geographically restricted identity evidence only, never supplementary route stops.
                for name in names if poi.id in SPECIAL_ALIASES else [poi.name_zh]:
                    types='140000|110000' if poi.id=='p24' else ('110000|190000' if poi.id=='p7' else '')
                    queries.append(dict(method='around_identity',keywords=name,location=asdict(Location(*poi.coordinates,'GCJ02')),types=types,radius=1000))
                    try:candidates.extend(provider.search_identity_near_coordinate(name,Location(*poi.coordinates,'GCJ02'),types=types))
                    except Exception as exc:errors.append(exc.code if isinstance(exc,ExternalProviderError) else 'provider_response_invalid')
                row=match_poi(poi,candidates,aliases=aliases,expected_district=expected)
            if poi.id=='p24':
                row.update(entity_type='memorial_museum',live_info_applicability='FULL')
                if row['identity_mapping_status']=='MATCHED':row.update(reviewed=True,match_method='MANUAL_ALIAS_CONFIRMATION',notes='Formal-name parent found; identity and aliases confirmed conditionally by project owner.')
                else:row.update(identity_mapping_status='NOT_FOUND',amap_poi_id=None,matched_name=None,match_method=None,notes='现实地点中国共产党第一次全国代表大会纪念馆存在；正式全称和三项 aliases 的上海名称检索、黄浦区/类型/附近检索未找到可信总主体。附属广场、公交站、保管部、实验室不绑定。')
        row.update(fetched_at=utc_now(),search_queries=queries,search_errors=errors)
        if errors:row['error_code']=errors[0]
        mappings[poi.id]=row
    PoiMappingRepository(records=mappings)
    counts=Counter(r['identity_mapping_status'] for r in mappings.values())
    applicability=Counter(r['live_info_applicability'] for r in mappings.values())
    summary=dict(total_core_pois=len(mappings),identity_counts={s:counts[s] for s in MappingStatus},live_info_applicability_counts={s:applicability[s] for s in LiveInfoApplicability},manual_review_required=[pid for pid,r in mappings.items() if r['identity_mapping_status']=='AMBIGUOUS' and not r['reviewed']],search_failures=[pid for pid,r in mappings.items() if r.get('error_code')],threshold=dict(min_confidence=.92,min_name_similarity=.9,max_distance_m=300,min_runner_up_margin=.08),source='live_amap_identity_calibration',identity_does_not_establish_venue_existence=True)
    return mappings,summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(DEFAULT_MAPPING_PATH))
    parser.add_argument('--audit-output',default='examples/location_awareness/mapping_audit.json')
    args=parser.parse_args()
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1' or not os.environ.get('AMAP_WEB_SERVICE_KEY','').strip():raise SystemExit('Live identity audit opt-in and service key required')
    path=Path(args.output);existing={}
    if path.exists():
        values=json.loads(path.read_text(encoding='utf-8'))
        existing={pid:r for pid,r in values.items() if 'identity_mapping_status' in r}
        if existing:PoiMappingRepository(records=existing)
    mappings,summary=audit(POIRepository(),AmapPoiProvider(AmapClient()),existing=existing)
    if summary['search_failures']:raise SystemExit('Incomplete provider search; sidecar not replaced. Retry audit.')
    for filename,data in ((args.output,mappings),(args.audit_output,summary)):
        p=Path(filename);p.parent.mkdir(parents=True,exist_ok=True)
        temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,p)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

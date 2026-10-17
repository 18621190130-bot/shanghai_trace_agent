"""External identities and live-information applicability are independent."""
import copy
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from .geo_utils import haversine_km
from .world_models import MappingStatus, LiveInfoApplicability

DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[1] / 'data/amap_poi_mappings.json'
MANUAL_METHODS = {'MANUAL_CONFIRMED','MANUAL_PARENT_CONFIRMATION','MANUAL_ALIAS_CONFIRMATION','MANUAL_COORDINATE_CORRECTION','MANUAL_SEMANTIC_SCOPE_CONFIRMATION'}
METHODS = MANUAL_METHODS | {'AUTO_HIGH_CONFIDENCE'}

class PoiMappingRepository:
    def __init__(self, path=DEFAULT_MAPPING_PATH, *, records=None):
        if records is None:
            path = Path(path)
            records = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(records,dict):raise ValueError('Mapping sidecar must be an object')
        for pid,row in records.items():
            if not isinstance(pid,str) or not isinstance(row,dict):raise ValueError('Invalid mapping entry')
            status = row.get('identity_mapping_status')
            if status not in set(MappingStatus):raise ValueError('Invalid identity mapping status')
            if row.get('live_info_applicability') not in set(LiveInfoApplicability):raise ValueError('Invalid live applicability')
            confidence = row.get('confidence',0)
            if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:raise ValueError('Invalid mapping confidence')
            if type(row.get('reviewed')) is not bool:raise ValueError('Mapping reviewed must be boolean')
            if not isinstance(row.get('aliases'),list) or any(not isinstance(a,str) for a in row['aliases']):raise ValueError('Invalid aliases')
            if not isinstance(row.get('entity_type'),str) or not isinstance(row.get('notes'),str):raise ValueError('Missing mapping metadata')
            method = row.get('match_method')
            if method is not None and method not in METHODS:raise ValueError('Invalid match method')
            if row['reviewed'] and method not in MANUAL_METHODS:raise ValueError('Reviewed mapping requires a manual method')
            provider_id = row.get('amap_poi_id')
            if status == MappingStatus.MATCHED:
                if not isinstance(provider_id,str) or not re.fullmatch(r'[A-Za-z0-9]{5,32}',provider_id):raise ValueError('MATCHED requires provider ID')
                if not row.get('matched_name') or method is None:raise ValueError('MATCHED requires provenance')
                if confidence < .92 and not row['reviewed']:raise ValueError('Low-confidence match requires explicit review')
            elif provider_id is not None:raise ValueError('Unresolved mapping must not bind a provider ID')
            distance = row.get('distance_m')
            if distance is not None and (isinstance(distance,bool) or not isinstance(distance,(int,float)) or not math.isfinite(distance) or distance<0):raise ValueError('Invalid mapping distance')
        self._records = copy.deepcopy(records)
    def get(self, core_poi_id):return copy.deepcopy(self._records.get(core_poi_id))

def normalized_name(name):
    name = re.sub(r'（含[^）]*）|\(including[^)]*\)|（石库门街区）', '', name)
    # Access notices annotate the same identity; they are never opening-hours evidence.
    name = re.sub(r'[（(](?:暂停开放|不对外开放|暂时关闭|暂停营业)[）)]', '', name)
    return re.sub(r'[\W_]', '', name.replace('上海市','').replace('上海','').lower())

def classify(poi):
    name = poi.name_zh
    if poi.poi_type == 'park':return 'park',LiveInfoApplicability.LIMITED
    if poi.id == 'p32':return 'church',LiveInfoApplicability.LIMITED
    if poi.id == 'p11':return 'historic_district',LiveInfoApplicability.LIMITED
    if poi.id == 'p4':return 'residence_museum',LiveInfoApplicability.FULL
    if '图书馆' in name or '书院' in name:return 'library',LiveInfoApplicability.FULL
    if '音乐厅' in name:return 'concert_hall',LiveInfoApplicability.FULL
    if '纪念馆' in name:return 'memorial_museum',LiveInfoApplicability.FULL
    if any(t in name for t in ('故居','公寓','司令部旧址','大楼')):return 'historic_building',LiveInfoApplicability.LIMITED
    if poi.id in ('p9','p23'):return 'historic_district',LiveInfoApplicability.LIMITED
    if poi.id == 'p15':return 'garden',LiveInfoApplicability.LIMITED
    if poi.id == 'p30':return 'commercial_complex',LiveInfoApplicability.FULL
    if poi.poi_type in ('street','district','landmark'):return ('street' if poi.poi_type=='street' else 'open_space'),LiveInfoApplicability.NOT_APPLICABLE
    return 'cultural_venue',LiveInfoApplicability.FULL

CHILD = re.compile(r'(?:[ABDN]\d*馆|北广场|少年(?:儿童)?馆|少年儿童馆|游客中心|观众服务中心|报告厅|专题展厅|宣誓大厅|初心教室|入口|出口|停车场|停车点|售票(?:处)?|子殿|三官殿|分馆|保管部|实验室|公交站|地铁站|卫生间|公共厕所)',re.I)
MERCHANT_TYPES = ('餐饮','购物服务','生活服务','公司企业','住宿服务')

def entity_compatible(poi,candidate):
    if CHILD.search(candidate.name):return False
    kind,_ = classify(poi)
    ptype = candidate.poi_type or ''
    if kind == 'memorial_museum':
        return not any(t in ptype for t in (*MERCHANT_TYPES,'公园广场','交通设施')) and '广场' not in candidate.name
    if kind=='park':return '公园' in candidate.name and not any(t in ptype for t in MERCHANT_TYPES)
    if kind in ('street','open_space','historic_district','garden'):
        # A characteristic commercial STREET/complex is an area parent, unlike its merchants.
        area_type = '特色商业街' in ptype or kind=='historic_district' and '购物服务;商场;商场' in ptype
        return area_type or not any(t in ptype for t in (*MERCHANT_TYPES,'酒吧','培训机构'))
    return True

def child_of(parent,child):
    return bool(CHILD.search(child['name'])) and normalized_name(parent['name']) in normalized_name(child['name'])


def geographic_representation(poi,row):
    """Resolve a road/plaza vs hotspot representation of the SAME geographic entity."""
    ptype = row.get('poi_type') or ''
    if poi.poi_type == 'street':
        if '道路名' in ptype:return 'road'
        if '城市广场' in ptype:return 'plaza'
        if '热点地名' in ptype or '风景名胜' in ptype:return 'geographic_hotspot'
    return None


def same_geographic_entity(poi,preferred,other):
    kind = geographic_representation(poi,preferred)
    other_kind = geographic_representation(poi,other)
    if kind not in ('road','plaza') or other_kind!='geographic_hotspot':return False
    if normalized_name(preferred['name'])!=normalized_name(other['name']):return False
    a,b=preferred['location'],other['location']
    return preferred['district']==other['district'] and haversine_km((a['lat'],a['lng']),(b['lat'],b['lng']))*1000<=60

def match_poi(poi, candidates, *, aliases=(), expected_district=None):
    from .geo_utils import to_gcj02
    # Spatial routing anchors do not redefine the provider identity's coordinate.
    identity_point = to_gcj02(*poi.original_coordinates,poi.original_coordinate_system)
    entity_type,applicability = classify(poi)
    base = dict(amap_poi_id=None,confidence=0,matched_name=None,distance_m=None,reviewed=False,
                core_name=poi.name_zh,zone=poi.zone_id,entity_type=entity_type,
                live_info_applicability=applicability,aliases=list(aliases),match_method=None,notes='')
    scored = []
    names = [normalized_name(n) for n in (poi.name_zh,*aliases) if n]
    for candidate in candidates:
        if identity_point is None:continue
        similarity = max(SequenceMatcher(None,n,normalized_name(candidate.name)).ratio() for n in names)
        distance = haversine_km(identity_point,(candidate.location.lat,candidate.location.lng))*1000
        district_ok = not expected_district or candidate.district == expected_district
        compatible = entity_compatible(poi,candidate)
        confidence = .75*similarity+.25*max(0,1-distance/1000)
        if not district_ok or not compatible:confidence *= .5
        scored.append(dict(**candidate.to_dict(),name_similarity=similarity,distance_m=distance,
                           confidence=confidence,district_consistent=district_ok,entity_type_compatible=compatible))
    scored.sort(key=lambda c:(-c['confidence'],c['distance_m'],c['provider_id']))
    unique = [];seen = set()
    for row in scored:
        if row['provider_id'] not in seen:unique.append(row);seen.add(row['provider_id'])
    plausible = [r for r in unique if r['name_similarity']>=.9 and r['distance_m']<=300 and r['district_consistent'] and r['entity_type_compatible']]
    if not plausible:return dict(base,identity_mapping_status=MappingStatus.NOT_FOUND,notes='Real-world Core retained; no credible provider parent identity found in these searches.',candidates=unique)
    best = plausible[0]
    # Prefer the explicit road/plaza category when an otherwise identical hotspot is present.
    for row in plausible:
        if same_geographic_entity(poi,row,best):best=row;break
    rivals = [r for r in unique if r['provider_id']!=best['provider_id'] and not child_of(best,r) and not same_geographic_entity(poi,best,r)]
    margin = best['confidence']-(rivals[0]['confidence'] if rivals else 0)
    trusted = best['confidence']>=.92 and margin>=.08
    status = MappingStatus.MATCHED if trusted else (MappingStatus.AMBIGUOUS if len(plausible)>1 else MappingStatus.NOT_FOUND)
    return dict(base,identity_mapping_status=status,amap_poi_id=best['provider_id'] if trusted else None,
                confidence=best['confidence'],matched_name=best['name'] if trusted else None,distance_m=best['distance_m'],match_method='AUTO_HIGH_CONFIDENCE' if trusted else None,
                notes='High-confidence parent identity; child entities excluded from competing-parent margin.' if trusted else ('Multiple plausible provider entities require identity review.' if status==MappingStatus.AMBIGUOUS else 'No sufficiently reliable provider identity; Core existence is not disputed.'),candidates=unique)

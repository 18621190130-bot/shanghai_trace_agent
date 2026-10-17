"""Cheap, evidence-independent hygiene before semantic API calls."""
import re
from .normalization import match_key

def prefilter_raw(raw, config):
    name=raw.name_zh or raw.name_en
    if re.search(r'停车|充电|售票|游客中心|卫生间|厕所|出入口|公交站|地铁站|培训|临时(?!政府.*旧址)|花卉节|快闪|售楼|便利店|打卡点|篮球场|网球场|壁球馆|匹克球', name):
        return 'ancillary_or_temporary'
    category=raw.source_category
    if re.search(r'餐饮服务|住宿服务|汽车服务|生活服务|体育休闲服务.*(健身|体育场)|购物服务.*(便利|超市|服装|专卖)',category):
        return 'generic_service_or_shop'
    if raw.raw_provider_tags.get('shop') and not raw.raw_provider_tags.get('historic'):
        return 'generic_shop'
    if raw.raw_provider_tags.get('amenity') in ('cafe','restaurant','fast_food','bank') and not raw.raw_provider_tags.get('historic'):
        return 'generic_service'
    return None

def prefilter_node(candidate):
    if candidate.get('internal_parent'): return 'child_or_internal_entity'
    if candidate.get('identity',{}).get('identity_status')!='new_candidate': return 'identity_not_resolved_new_node'
    if candidate.get('entity_no_longer_exists') or re.search(r'永久关闭|永久停业|已拆除|已撤除|活动已结束',candidate.get('name_zh','')): return 'entity_no_longer_exists'
    if not candidate.get('coordinates'): return 'location_unresolved'
    if candidate['boundary_status']=='outside_pilot': return 'outside_product_boundary'
    if candidate['boundary_status']=='needs_review': return 'needs_boundary_review'
    official=[r for r in candidate['merged_source_records'] if r['source_type'] in ('official','government') and r.get('snippets')]
    # Map category alone is insufficient to pay for high-value semantic claims.
    if not official: return 'insufficient_evidence'
    return None

def normalized_name(name):
    return re.sub(r'(不对外开放|暂时关闭|暂停营业|上海市|上海|市)$','',match_key(name)).replace('上海','')

def physical_stability(candidate,semantic):
    """Permanent public geography is separate from live venue access.

    Do not override an explicit temporary/disappearance signal. A retrieved
    map street/park plus authority description supports medium permanence;
    missing opening times alone do not make a street a temporary event.
    """
    disappeared=candidate.get('entity_no_longer_exists') or re.search(r'永久关闭|永久停业|已拆除|已撤除|活动已结束',candidate['name_zh'])
    if disappeared or candidate.get('entity_stability')=='temporary':return dict(accepted=False,basis='explicit_entity_disappearance_or_temporary',confidence='high')
    if semantic['stability']=='stable':return dict(accepted=True,basis='validated_semantic_stable',confidence='medium')
    records=candidate['merged_source_records']
    mapped=any(r['source_type']=='amap' for r in records)
    authority=any(r['source_type'] in ('official','government') and r.get('snippets') for r in records)
    physical=semantic['category']=='park' or candidate['entity_kind']=='street' or any('道路名' in r['source_category'] or r['raw_provider_tags'].get('highway')=='pedestrian' for r in records)
    negative=re.search(r'临时(?!政府.*旧址)|快闪|活动已结束',candidate['name_zh'])
    accepted=semantic['stability']=='unknown' and mapped and authority and physical and not negative
    return dict(accepted=bool(accepted),confidence='medium' if accepted else 'low',basis='current_map_and_authority_support_permanent_public_geography; live_access_unknown' if accepted else 'permanence_unresolved')

"""Prevent an article's whole-route claims from becoming a single POI's tags."""
import copy,re

def validate_subject_scope(semantic,candidate):
    value=copy.deepcopy(semantic); removed=[]
    records=candidate.get('merged_source_records',[])
    mapped_categories=' '.join(r['source_category'] for r in records if r['source_type'] in ('amap','osm'))
    own_name=candidate.get('name_zh','')
    for proposal in value['tag_evidence']:
        texts=[str(candidate['evidence_catalog'][r]['value']) for r in proposal['evidence_refs']]
        if texts and all(re.search(r'本条路线|路线也途经|沿途也可以',t) for t in texts):
            removed.append(dict(group=proposal['group'],tag=proposal['tag'],reason='route_overview_is_not_subject_specific_evidence'))
        elif proposal['tag']=='parks' and not(re.search(r'公园|leisure=(park|garden)',mapped_categories) or '公园' in own_name):
            removed.append(dict(group=proposal['group'],tag=proposal['tag'],reason='nearby_park_or_visible_greenery_does_not_make_this_subject_a_park'))
        elif proposal['tag'] in ('shopping_lifestyle','shopping_leisure') and not re.search(r'购物|商业街|商场|shopping|mall|retail',mapped_categories,re.I):
            removed.append(dict(group=proposal['group'],tag=proposal['tag'],reason='nearby_commercial_road_does_not_establish_subject_shopping_experience'))
    keys={(r['group'],r['tag']) for r in removed}
    for group in ('interest_tags','experience_tags','culture_tags'):
        value[group]=[t for t in value[group] if (group,t) not in keys]
    value['tag_evidence']=[p for p in value['tag_evidence'] if (p['group'],p['tag']) not in keys]
    value['subject_scope_validation']=dict(removed_tags=removed,policy='Only the individual POI, not other places in the source itinerary, may support a tag.')
    return value

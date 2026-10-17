"""Evidence-specific, deterministic adjudication of the requested repair nodes.

Policies below are review proposals, not automatic production truth. New factual
claims are not introduced. Full legacy semantic validation still applies.
"""
import copy
import hashlib
import json
import re
from .schema import ROLES,FACTS
from .validation import validate_semantic_enrichment
from .preparation import geographic_context


def plan(category,role,tags,reason,*,confidence='medium',decision='needs_review',independent='medium',minutes=(5,15,25)):
    return dict(category=category,primary=role,tags=tags,reason=reason,confidence=confidence,
                decision=decision,independent=independent,minutes=minutes)


# Each tag is paired with an explicit evidence selector. This is a reviewed
# policy table, not a category-to-tag mapper or a coverage optimizer.
PLANS={
 '西岸艺术中心':plan('cultural_venue','supporting_stop',{
     'art':r'西岸艺术中心A馆前身', 'industrial_heritage':r'飞机制造厂冲压车间', 'architecture':r'保留了建筑',
     'adaptive_reuse':r'西岸艺术中心A馆前身', 'architecture_detail':r'保留了建筑',
     'industrial_transformation':r'西岸艺术中心A馆前身'},
     '官方说明保留飞机制造厂冲压车间的建筑与工业空间，并承载文化活动。可独立观察再利用空间，作为滨江主题的补充站；展览内容和可进入范围未核实，暂不将其当作主目的地。',decision='recommended_accept'),
 '西岸穹顶艺术中心（含北广场）':plan('performance_venue','supporting_stop',{'art':r'amenity=theatre'},
     '一个节点保留两种访问范围：广场外部短停与场馆访问。广场与场馆相邻但非同一体验；尚无证据支持将其拆成两个独立 stops，演出和进入条件待核实。'),
 '滨江滑板公园':plan('park','supporting_stop',{
     'parks':r'公园广场;公园|leisure=park','waterfront':r'徐汇滨江滑板公园',
     'riverside_walk':r'徐汇滨江滑板公园','social_observation':r'本地滑板社群的重要聚集地',
     'public_life':r'本地滑板社群的重要聚集地'},
     '官方描述专业户外场地及本地滑板社群聚集，可有目的地观察公共活动；不是仅因位于滨江赋予社会观察标签。多源坐标为不同代表点，入口和观察边界仍需核对。'),
 '徐汇跑道公园':plan('park','supporting_stop',{
     'parks':r'leisure=park|跑道公园以机场跑道', 'history':r'航空历史印迹',
     'adaptive_reuse':r'原龙华机场跑道转变', 'street_scene':r'街道和公园组织',
     'urban_renewal':r'原龙华机场跑道转变'},
     '官方说明机场跑道转为街道、公园及多种交通休闲空间；可作为独立的线性空间观察站。水系不等于黄浦江滨水路线，因此移除 waterfront/riverside_walk；试点边界仍待核实。',minutes=(10,20,35)),
 '上海摄影艺术中心':plan('cultural_venue','supporting_stop',{
     'art':r'上海摄影艺术中心位于', 'architecture':r'上海摄影艺术中心位于',
     'museum_visit':r'美术馆规格的摄影艺术场馆'},
     '官方说明摄影场馆的独立内容和空间，中文与英文记录均指向龙腾大道同一门牌。适合有目的的摄影艺术补充访问；当前展览、开门及入口需另核实，不因相邻艺术中心就计作其分馆。',decision='recommended_accept',minutes=(10,20,35)),
 '谷地花溪':plan('public_space','transition_stop',{'waterfront':r'这片位于瑞宁路243号', 'riverside_walk':r'这片位于瑞宁路243号'},
     '官方描述滨江绿地、铁轨遗迹及与滑板公园相邻，适合短时景观/遗迹观察。绿地描述不能直接证明 parks；缺少坐标，因此不能参与路线选点。',independent='low',minutes=(5,10,15)),
 '徐汇滨江海事塔广场':plan('public_space','transition_stop',{'waterfront':r'徐汇滨江海事塔广场','riverside_walk':r'徐汇滨江海事塔广场'},
     '地图确认滨江城市广场身份，空间位置可补充两处较强节点之间的短停；没有独立展览或复杂历史内容证据，故不提议 anchor。可达范围待核实。',independent='low',minutes=(5,10,15)),
 '北票码头塔吊':plan('heritage','transition_stop',{'industrial_heritage':r'北票码头塔吊','waterfront':r'北票码头塔吊','riverside_walk':r'徐汇滨江公共开放空间'},
     '塔吊及公共滨江地址支持工业构筑物的短时观察；设备不是因为视觉上有艺术感就成为 art。与塔吊广场的身份/范围关系未确证，不同时计作两站。',independent='low',minutes=(5,10,15)),
 '塔吊广场':plan('public_space','transition_stop',{'waterfront':r'沿着滨江步道','riverside_walk':r'沿着滨江步道'},
     '官方只支持滨江步道沿线的标志性景观，未描述独立公共艺术；移除 art/photogenic。可能是北票码头塔吊周边空间，缺坐标且关系未确证，暂不独立选点。',independent='low',minutes=(5,10,15)),
 '无尽影院':plan('public_art','transition_stop',{'art':r'tourism=artwork|^artwork$','photogenic':r'tourism=artwork'},
     'OSM 明确记录具名 installation artwork，可支持短时作品观察；不是仅凭工业设备名称判断为艺术。公共可达性和长期保留情况未核实，不能据此假设 museum_visit。',independent='low',minutes=(5,10,15)),
 '优秀历史建筑龙腾大道2555号':plan('heritage','transition_stop',{'history':r'优秀历史建筑龙腾大道2555号','architecture':r'优秀历史建筑龙腾大道2555号'},
     '地图名称提供历史建筑线索，但没有独立历史认定文件或建筑细节；与艺术中心场地及地址接近，先作为可能内部建筑核实，不独立增加 stop。',independent='low',minutes=(5,10,15)),
 '西岸运动公园':plan('park','supporting_stop',{'parks':r'公园广场;公园'},
     '地图公园类别支持 parks，但与滑板公园相邻，暂无独立功能范围的证据。两者是否同一运动空间待确认，不用重复公园条目增加 stops。'),
 '星扬公园':plan('park','transition_stop',{'parks':r'公园广场;公园'},
     '地图确认公园，可提议短时绿地停留；无安静、社会活动或历史证据，不补 quiet_walk/public_life。开放边界和独立步行价值待核实。',independent='low',minutes=(5,10,15)),
 '西岸中央公园':plan('park','supporting_stop',{'parks':r'^西岸中央公园$'},
     '仅有官方名称提及，公园身份可作为核查线索，缺位置、规模和活动内容；角色仅为低置信提议，暂不能参加路线选点。',confidence='low'),
 '西岸大剧院':plan('performance_venue','supporting_stop',{'art':r'影剧院;剧场|amenity=theatre'},
     '演艺用途有地图与OSM支持，可提出独立演艺访问的补充节点；但节目、入口及实际访问内容未核实。没有建筑细节证据，删除 architecture_detail；不凭剧院类别提升为 anchor。',confidence='low',minutes=(10,20,30)),
 '西岸漩心':plan('museum','supporting_stop',{'art':r'tourism=museum','museum_visit':r'tourism=museum'},
     'OSM提供具名文化场所线索，位置与既有强节点相邻；仅能提出文化访问补充站，缺少独立内容描述，不能确定 anchor。building=yes 不是建筑体验证据，删除 architecture。',confidence='low',minutes=(10,20,30)),
 '龙华码头':plan('public_space','transition_stop',{'waterfront':r'港口码头|龙华码头'},
     '地图港口码头身份支持滨水线索，但没有公共游览及可达证据。仅为条件性的短停提议，不能把港口设施直接视为独立目的地。',confidence='low',independent='low',minutes=(5,10,15)),
}

LOW_VALUE={'FISEHOOD极限运动公园','攀岩抱石区','岩时攀岩(Gate M西岸梦中心)','乐动力西岸活力谷','西岸国际会展中心(上海)'}


def pick(catalog,pattern):
    matched=[(ref,a) for ref,a in catalog.items() if isinstance(a['value'],str) and re.search(pattern,a['value'],re.I)]
    matched.sort(key=lambda item:(item[1]['source_type'] not in ('official','government'),item[1]['group'] not in ('official','history','public_space'),len(str(item[1]['value']))))
    return [ref for ref,_ in matched[:1]]


def production_evidence(node):
    raw=node['production_snapshot']
    catalog=node['evidence_catalog']
    pid=raw['id']
    for field,value in [('name_zh',raw['name']['zh']),('description',raw['content']['summary_zh']),
                        ('visit_profile',json.dumps(raw['visit_profile'],ensure_ascii=False)),
                        ('visit_scope',json.dumps(raw['visit_mode_details'],ensure_ascii=False)),
                        ('coordinates',dict(coordinates=node['coordinates'],coordinate_system='GCJ-02'))]:
        ref='production:'+pid+':'+field
        catalog[ref]=dict(record_id='production:'+pid,source_type='production',source_name='ShanghaiTrace frozen KB',
            url='data/pois.json#'+pid,retrieved_at=raw['verification'].get('checked_on'),group='identity' if field=='name_zh' else 'coordinates' if field=='coordinates' else 'history',field=field,value=value)
    return catalog


def production_role(node):
    raw=node['production_snapshot']
    modes=raw['visit_profile']['modes']
    full=modes.get('full_visit',{}).get('standard')
    role='anchor' if full and full>=60 else 'supporting_stop'
    reason=(f"既有 production 内容：{raw['content']['summary_zh']} 结合已校准 full_visit standard {full} 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。")
    return dict(primary=role,eligible=['anchor','supporting_stop'] if role=='anchor' else ['supporting_stop'],confidence='medium',
        independent_destination_value='high' if role=='anchor' else 'medium',route_connector_value='medium',reason=reason,
        evidence_refs=['production:'+raw['id']+':description','production:'+raw['id']+':visit_profile','production:'+raw['id']+':visit_scope'],
        alternatives_reason=dict(anchor='独立内容与既有完整访问时长共同支持。',supporting_stop='外部 walk_stop 范围可在更长路线中作补充。',transition_stop='完整节点具有独立主题和停留内容，不宜因缩短访问就新增一个过渡 stop。'))


def build_review(nodes,registry,old_rows,repository):
    old={r['candidate_id']:r for r in old_rows}
    taxonomy=repository.taxonomy
    result=[]
    for node in nodes:
        catalog=node['evidence_catalog']
        identity=node['identity']
        members=[old[cid] for cid in node['member_candidate_ids']]
        before_tags={g:sorted({t for row in members for t in row[g]}) for g in taxonomy}
        before_roles=sorted({r['route_role']['primary'] for r in members})
        sources={s.get('url'):s for s in node['sources']}
        base=dict(node_id=node['node_id'],name=node['name'],identity_status=identity['identity_status'],
            production_match=identity.get('production_match'),route_selectable=False,parent_node=None,
            sources=list(sources.values()),coordinates=node['coordinates'],coordinate_system='GCJ-02',
            source_confidence=dict(existence='high' if any(s['source_type'] in ('amap','official','government') for s in node['sources']) else 'medium',
                                   current_access='unknown'),identity_resolution=identity,member_candidate_ids=node['member_candidate_ids'],
            internal_entity_ids=node['internal_entities'],consolidation_reason=node['consolidation_reason'],
            evidence_catalog=catalog,admission_scope='new_route_node',production_imported=False)
        if node.get('production_id'):
            catalog=production_evidence(node)
            raw=node['production_snapshot']
            role=production_role(node)
            base.update(category=raw['category'],**copy.deepcopy(raw['tags']),route_role=role,
                decision='needs_review',reason=['existing_production_role_audit_only; not a new admission candidate'],
                route_selectable=True,counts_as_new_stop=False,admission_scope='production_audit_only',
                semantic_confidence='medium',production_snapshot=raw,evidence_catalog=catalog,
                visit_profile=raw['visit_profile'],visit_scope=raw['visit_mode_details'],
                tag_audit_status='production tags preserved; no factual edits proposed',
                semantic_method='production_preservation_plus_role_audit',
                targeted_answers=dict(independent_node=True,duplication='existing production parent; source children nonselectable',
                    diversity='audit only; adds zero POIs',tags_removed='none from production'))
        else:
            policy=PLANS.get(node['name'])
            semantic=None
            if policy:
                tag_evidence=[]
                tags={g:[] for g in taxonomy}
                unmatched=[]
                for tag,pattern in policy['tags'].items():
                    refs=pick(catalog,pattern)
                    group=next(g for g,v in taxonomy.items() if tag in v)
                    if not refs:
                        unmatched.append(tag)
                        continue
                    tags[group].append(tag)
                    tag_evidence.append(dict(group=group,tag=tag,evidence_refs=refs))
                role=dict(primary=policy['primary'],eligible=[policy['primary']],confidence=policy['confidence'],reason=policy['reason'],
                    independent_destination_value=policy['independent'],route_connector_value='medium',
                    alternatives_reason={r:('当前提议。'+policy['reason'] if r==policy['primary'] else
                        '现有访问范围、停留尺度及独立内容不足以优先采用该角色；不能仅凭类别或覆盖缺口升级。') for r in ROLES})
                refs=list(dict.fromkeys(ref for item in tag_evidence for ref in item['evidence_refs']))
                summary_ref=next((ref for ref,a in catalog.items() if a['field']=='snippet' and len(str(a['value']))>25),None)
                summary_ref=summary_ref or next(ref for ref,a in catalog.items() if isinstance(a['value'],str))
                profile=dict(walk_stop=dict(zip(('quick','standard','deep'),policy['minutes'])),full_visit=None,
                    time_basis='product_planning_estimate',scope=policy['reason'])
                if node['node_id']=='route:dome':
                    profile['full_visit']=dict(quick=30,standard=60,deep=90)
                    profile['scope']='walk_stop: exterior/north plaza; full_visit: venue/performance only when an event and access are verified; estimates, not factual performance duration'
                output=dict(category=policy['category'],**tags,tag_evidence=tag_evidence,category_evidence_refs=refs or [summary_ref],
                    route_role=role,citywalk_value=dict(level='medium',reason=policy['reason'],evidence_refs=refs or [summary_ref]),
                    summary_draft=dict(text=catalog[summary_ref]['value'],evidence_refs=[summary_ref]),culture_bridge_draft=None,
                    visit_profile_proposal=profile,semantic_confidence=policy['confidence'],stability='unknown',
                    missing_information=['current public access and exact visit scope require human review']+unmatched,
                    factual_fields={f:None for f in FACTS},taxonomy_extension_candidate=[])
                semantic=validate_semantic_enrichment(output,node,catalog,taxonomy)
                base.update(category=policy['category'],**tags,route_role=role,semantic=semantic,semantic_confidence=policy['confidence'],
                    decision=policy['decision'],reason=[policy['reason']],route_selectable=bool(node['coordinates']),counts_as_new_stop=bool(node['coordinates']),
                    visit_profile=profile,tag_audit_status='explicit evidence selectors + unchanged strict validator',
                    semantic_method='targeted_deterministic_evidence_review',
                    targeted_answers=dict(independent_node='proposed' if node['coordinates'] else 'potential; location unresolved',
                        duplication=node['consolidation_reason'],diversity='existing evidence supports '+', '.join(t for ts in tags.values() for t in ts)))
                if unmatched:
                    base['decision']='needs_review'
                    base['reason'].append('requested tag selector had no evidence: '+','.join(unmatched))
            else:
                # Unchanged candidates retain only previously validated proposals.
                previous=members[0]
                semantic=copy.deepcopy(previous['semantic'])
                tags={g:list(previous[g]) for g in taxonomy}
                base.update(category=previous['category'],**tags,semantic=semantic,route_role=copy.deepcopy(previous['route_role']),
                    semantic_confidence=previous['semantic_confidence'],decision='needs_review',reason=['既有校验结果复用；未新增模型调用。仍需确认独立访问范围。'],
                    route_selectable=bool(node['coordinates']),counts_as_new_stop=bool(node['coordinates']),
                    visit_profile=semantic.get('visit_profile_proposal') if semantic else None,
                    tag_audit_status='previous validated tags reused; no enrichment rerun',
                    semantic_method='reuse_validated_phase2_5B',
                    targeted_answers=dict(independent_node='unconfirmed',duplication=node['consolidation_reason'],diversity='not assumed'))
                if not any(tags.values()):
                    base.update(decision='reject',route_selectable=False,counts_as_new_stop=False,
                        reason=['无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。'])
            if identity['identity_status'] in ('possible_duplicate','unresolved'):
                base.update(route_selectable=False,counts_as_new_stop=False,decision='needs_review')
                base['reason'].append('identity or production relationship unresolved; cannot become a new stop')
            if node['name']=='塔吊广场':
                base.update(identity_status='possible_duplicate',related_node='route:wb_fd436a54b9d249a2',route_selectable=False,counts_as_new_stop=False)
            if node['name']=='优秀历史建筑龙腾大道2555号':
                base.update(identity_status='possible_duplicate',parent_node='route:art_center',parent_relation_status='unconfirmed',route_selectable=False,counts_as_new_stop=False)
            if node['name']=='西岸运动公园':
                base.update(identity_status='possible_duplicate',related_node='route:skate',route_selectable=False,counts_as_new_stop=False)
            if not node['coordinates']:
                base.update(route_selectable=False,counts_as_new_stop=False)
            if node['boundary_status']=='outside_pilot':
                base.update(decision='reject',route_selectable=False,counts_as_new_stop=False)
                base['reason'].append('outside West Bund pilot boundary')
            if node['boundary_status']=='needs_review' or (node['coordinate_conflict_m']>120 and node['node_id']!='route:art_center'):
                base['decision']='needs_review' if base['decision']!='reject' else 'reject'
                base['reason'].append('pilot boundary or differing representative coordinates need verification')
        base['primary_role']=base['route_role']['primary']
        base['eligible_roles']=base['route_role']['eligible']
        base['role_confidence']=base['route_role']['confidence']
        base['tag_changes']={g:dict(before=before_tags[g],after=base[g],removed=sorted(set(before_tags[g])-set(base[g])),
                                   added=sorted(set(base[g])-set(before_tags[g]))) for g in taxonomy}
        base['role_changes']=dict(before=before_roles,after=base['primary_role'],basis=base['route_role']['reason'])
        base['coordinate_observations']=node['coordinate_observations']
        base['geographic_context']=geographic_context(node,nodes,repository.get_pois_by_zone('west_bund'))
        base['role_evidence_refs']=base['route_role'].get('evidence_refs',
            list(dict.fromkeys(ref for item in (base.get('semantic') or {}).get('tag_evidence',[]) for ref in item['evidence_refs'])))
        if base['admission_scope']=='new_route_node':
            covered={g:{tag for poi in repository.get_pois_by_zone('west_bund') for tag in getattr(poi,g)} for g in taxonomy}
            gains={g:[t for t in base[g] if t not in covered[g]] for g in taxonomy}
            base['targeted_answers'].update(primary_role=base['primary_role'],strong_tags={g:base[g] for g in taxonomy},
                removed_tags={g:base['tag_changes'][g]['removed'] for g in taxonomy},
                diversity_gain=gains,diversity_note='descriptive comparison after tag adjudication, never evidence for tag assignment')
        result.append(base)
    return result

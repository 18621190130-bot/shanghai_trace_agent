"""Route-level consolidation with an audit registry of all source entities."""
import copy
from ...geo_utils import haversine_km
from .identity import ProductionIdentityResolver

GROUPS = [
    ('art_center','西岸艺术中心','西岸艺术中心（含A馆）',
     ['西岸艺术中心（含A馆）','西岸艺术中心B1馆','西岸艺术中心N馆','西岸艺术中心D馆'],
     '用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。'),
    ('dome','西岸穹顶艺术中心（含北广场）','西岸穹顶艺术中心（含北广场）',
     ['西岸穹顶艺术中心（含北广场）'],
     'Option 1：一个节点，不同 visit scope。广场在场馆北侧约84米；没有足够证据证明两次独立 City Walk 体验。'),
    ('skate','滨江滑板公园','上海市滨江滑板公园',
     ['滨江滑板公园','上海市滨江滑板公园'],
     '官方描述同名徐汇滨江户外滑板场；Amap/OSM 公园名与邻近位置相符。合并身份，但不同代表坐标保留供入口核实。'),
    ('runway','徐汇跑道公园','徐汇跑道公园',
     ['跑道公园','徐汇跑道公园'],
     '官方机场跑道改造公园与 OSM 徐汇跑道公园的专名、区域及公园用途一致；官方记录无坐标，明确保留位置边界待核实。'),
    ('photography','上海摄影艺术中心','Shanghai Center of Photography',
     ['上海摄影艺术中心','Shanghai Center of Photography'],
     '官方中文专名与 OSM 英文专名对应，均指向龙腾大道2555号；官方细分地址为2555号-1，合并为一个摄影场馆节点。'),
]


class RouteNodeConsolidator:
    def __init__(self,repository):
        self.repository=repository
        self.resolver=ProductionIdentityResolver(repository)

    def consolidate(self,candidates,review_rows):
        candidates=copy.deepcopy(candidates)
        rows={r['candidate_id']:r for r in review_rows}
        identities={c['candidate_id']:self.resolver.resolve(c) for c in candidates}
        nodes,registry,used=[],[],set()

        def build(node_id,name,members,primary,reason,identity,production_id=None):
            primary=primary or members[0]
            node=copy.deepcopy(primary)
            node.update(node_id=node_id,name=name,identity=identity,production_id=production_id,
                member_candidate_ids=[c['candidate_id'] for c in members],consolidation_reason=reason,
                sources=[],evidence_catalog={},coordinate_observations=[],internal_entities=[])
            for member in members:
                cid=member['candidate_id']
                used.add(cid)
                node['sources']+=member['sources']
                node['evidence_catalog'].update(rows[cid]['evidence_catalog'])
                if member.get('coordinates'):
                    node['coordinate_observations'].append(dict(candidate_id=cid,coordinates=member['coordinates']))
                entry=dict(entity_id=cid,name=member['name_zh'] or member['name_en'],parent_node=node_id,
                    route_selectable=False,relationship='source_representation_or_internal_entity',
                    source_records=member.get('merged_source_records',[]),identity=identities[cid],reason=reason)
                registry.append(entry)
                node['internal_entities'].append(cid)
                for component in member.get('component_candidates',[]):
                    registry.append(dict(entity_id=component['candidate_id'],name=component['name'],parent_node=node_id,
                        route_selectable=False,relationship='previously_grouped_component',coordinates=component['coordinates'],reason=reason))
            node['coordinate_conflict_m']=max((haversine_km(a['coordinates'],b['coordinates'])*1000
                for a in node['coordinate_observations'] for b in node['coordinate_observations']),default=0)
            nodes.append(node)
            return node

        # Production parents are an audit population, never new admission nodes.
        for pid in ('p5','p28','p29','p30','p31'):
            members=[c for c in candidates if identities[c['candidate_id']]['identity_status']=='existing_production' and identities[c['candidate_id']]['production_match']==pid]
            raw=next(p for p in self.repository.get_raw_data()['pois'] if p['id']==pid)
            if not members:
                raise ValueError('Expected production audit sources for '+pid)
            primary=next((c for c in members if any(s['source_type']=='amap' for s in c['sources'])),members[0])
            node=build('production:'+pid,raw['name']['zh'],members,primary,'已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。',
                       dict(identity_status='existing_production',production_match=pid,confidence='high'),pid)
            node['production_snapshot']=copy.deepcopy(raw)
            node['coordinates']=list(self.repository.get_poi_by_id(pid).coordinates)
            node['coordinate_system']='GCJ-02'
            node['boundary_status']='existing_production_scope'

        for key,name,primary_name,names,reason in GROUPS:
            members=[c for c in candidates if c['candidate_id'] not in used and (c['name_zh'] in names or c['name_en'] in names)]
            if not members:
                continue
            # Closed pilot rules still fail closed on contradictory geometry.
            points=[c['coordinates'] for c in members if c['coordinates']]
            extent=max((haversine_km(a,b) for a in points for b in points),default=0)
            limit=.6 if key=='art_center' else .4
            if extent>limit:
                for member in members:
                    identities[member['candidate_id']]=dict(identity_status='possible_duplicate',production_match=None,
                        confidence='low',evidence=dict(reason='named group has conflicting geometry',proposed_group=key,extent_km=extent))
                continue
            primary=next((c for c in members if (c['name_zh']==primary_name or c['name_en']==primary_name) and c['coordinates'] and any(s['source_type']=='amap' for s in c['sources'])),None)
            primary=primary or next((c for c in members if c['coordinates']),members[0])
            build('route:'+key,name,members,primary,reason,
                  dict(identity_status='new_candidate',production_match=None,confidence='high' if key in ('art_center','dome','photography') else 'medium'))

        # Containment is distinct from identity; it is not a name-only POI merge.
        parent_specs={
            '徐汇油罐艺术公园':('production:p29','同园区户外体验已由 p29.walk_stop 明确覆盖；未证明独立站点。'),
            '南浦站':('production:p31','production 描述原铁路南浦站仓库；候选与星美术馆代表坐标相邻，缺少独立 stop 证据。'),
            '岩时攀岩(Gate M西岸梦中心)':('production:p30','地址为龙腾大道2266号内部商户；无独立 City Walk 价值证据。'),
            '开心麻花大三角剧场(Gate M西岸梦中心)':('production:p30','同地址园区内部演艺场所；缺少独立入口与作为新 City Walk stop 的证据。'),
            '西岸梦中心·梦工场':('production:p30','2266号园区楼层实体，不独立增加 City Walk stops。'),
            '瓦肆 VAS est':('production:p30','OSM 地址龙腾大道2266，当前仅演艺类别，未证明独立街行节点。'),
        }
        for candidate in candidates:
            cid=candidate['candidate_id']
            if cid in used:
                continue
            name=candidate['name_zh'] or candidate['name_en']
            if name in parent_specs:
                parent,reason=parent_specs[name]
                registry.append(dict(entity_id=cid,name=name,parent_node=parent,route_selectable=False,
                    relationship='internal_entity',reason=reason,source_records=candidate['merged_source_records'],identity=identities[cid],
                    decision='reject_as_independent_route_node'))
                target=next(n for n in nodes if n['node_id']==parent)
                target['internal_entities'].append(cid)
                target['member_candidate_ids'].append(cid)
                target['sources']+=candidate['sources']
                target['evidence_catalog'].update(rows[cid]['evidence_catalog'])
                used.add(cid)
            else:
                build('route:'+cid,name,[candidate],candidate,'保留为独立候选；是否可选由身份、证据、访问范围和边界决定。',identities[cid])
        return nodes,registry,identities

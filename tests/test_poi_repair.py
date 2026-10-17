from .helpers import baseline_repository, PRE_PHASE2_5_PATH
"""Offline fixtures; never call collection or a real DeepSeek provider."""
import copy
import json
import unittest
from src.poi_repository import POIRepository
from src.llm_client import MockLLMClient
from src.models import RequestValidationError
from src.poi_pipeline.semantic.identity import ProductionIdentityResolver
from src.poi_pipeline.semantic.consolidation import RouteNodeConsolidator
from src.poi_pipeline.semantic.repair_policy import TargetedRetryPolicy,TargetedSemanticRepair,compact_evidence,historical_failures
from src.poi_pipeline.semantic.repair_review import build_review
from src.poi_pipeline.semantic.validation import validate_semantic_enrichment
from .test_poi_semantic import fixtures as semantic_fixtures


def candidate(cid,name,coordinates=(31.17,121.463),*,name_en='',address='龙腾大道2555号'):
    return dict(candidate_id=cid,name_zh=name,name_en=name_en,aliases=[],coordinates=list(coordinates) if coordinates else None,
        coordinate_system='GCJ-02',address=address,boundary_status='inside_pilot',entity_kind='venue',issues=[],
        field_sources=dict(coordinates='amap:'+cid),sources=[dict(source_type='amap',source_name='fixture',url='https://example.org/'+cid,retrieved_at='fixture',supports=['identity'])],
        merged_source_records=[dict(source_type='amap',source_candidate_id=cid,name_zh=name,raw_provider_tags={})])


def fixture_set(repo):
    data=[]
    for p in repo.get_pois_by_zone('west_bund'):
        data.append(candidate(p.id,p.name_zh,p.coordinates,name_en=p.name_en,address=''))
    return data


def rows_for(data):
    return [dict(candidate_id=c['candidate_id'],evidence_catalog={},interest_tags=[],experience_tags=[],culture_tags=[],
        route_role=dict(primary='supporting_stop'),run=dict(attempts=[])) for c in data]


class ProductionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.repo=baseline_repository()
        self.resolver=ProductionIdentityResolver(self.repo)

    def test_all_five_bilingual_matches(self):
        names={'p5':'Long Museum (West Bund)','p28':'West Bund Museum','p29':'TANK Shanghai',
               'p30':'Gate M West Bund Dream Center','p31':'START Museum'}
        for pid,name in names.items():
            p=self.repo.get_poi_by_id(pid)
            for zh,en in [(p.name_zh,''),('',name)]:
                result=self.resolver.resolve(candidate('fixture',zh,p.coordinates,name_en=en,address=''))
                self.assertEqual(result['identity_status'],'existing_production')
                self.assertEqual(result['production_match'],pid)

    def test_alias_and_normalized_name(self):
        p=self.repo.get_poi_by_id('p29')
        c=candidate('tank','different label',p.coordinates)
        c['aliases']=['  TANK   Shanghai  ']
        self.assertEqual(self.resolver.resolve(c)['production_match'],'p29')

    def test_name_only_is_possible_duplicate_not_new(self):
        result=self.resolver.resolve(candidate('missing','西岸美术馆',None,address=''))
        self.assertEqual(result['identity_status'],'possible_duplicate')

    def test_address_corroborates_missing_geometry(self):
        result=self.resolver.resolve(candidate('address','西岸美术馆',None,address='徐汇区龙腾大道2600号'))
        self.assertEqual(result['identity_status'],'existing_production')

    def test_official_source_identity_corroborates(self):
        c=candidate('official','西岸美术馆',None,address='')
        c['sources']=[dict(source_type='official',url='https://www.westbund.com/cn/index/KEY-PROJECTS/detail_695y4T.html')]
        self.assertEqual(self.resolver.resolve(c)['identity_status'],'existing_production')
        c['sources'][0]['url']='https://untrusted.example/detail_695y4T.html'
        self.assertEqual(self.resolver.resolve(c)['identity_status'],'possible_duplicate')

    def test_known_provider_id_and_explicit_id(self):
        resolver=ProductionIdentityResolver(self.repo,{'amap:known':'p28'})
        c=candidate('known','旧显示名称',None,address='')
        self.assertEqual(resolver.resolve(c)['production_match'],'p28')
        c=candidate('other','alternate',None,address='')
        c['production_id']='p31'
        self.assertEqual(resolver.resolve(c)['production_match'],'p31')

    def test_far_geometry_conflict_does_not_accept(self):
        c=candidate('far','西岸美术馆',(31.25,121.50),address='龙腾大道2600号')
        self.assertEqual(self.resolver.resolve(c)['identity_status'],'possible_duplicate')

    def test_new_unresolved_and_brand_collision(self):
        self.assertEqual(self.resolver.resolve(candidate('new','独立测试广场'))['identity_status'],'new_candidate')
        self.assertEqual(self.resolver.resolve(candidate('unknown','不明地点',None))['identity_status'],'unresolved')
        self.assertEqual(self.resolver.resolve(candidate('brand','GATE M 西岸凤巢'))['identity_status'],'possible_duplicate')


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.repo=baseline_repository()

    def run_group(self,extra):
        data=fixture_set(self.repo)+extra
        original=copy.deepcopy(data)
        nodes,registry,identities=RouteNodeConsolidator(self.repo).consolidate(data,rows_for(data))
        self.assertEqual(data,original)
        return nodes,registry,identities

    def test_art_center_children_add_only_one_stop(self):
        extra=[candidate(str(i),name) for i,name in enumerate(['西岸艺术中心（含A馆）','西岸艺术中心B1馆','西岸艺术中心N馆','西岸艺术中心D馆'])]
        nodes,registry,_=self.run_group(extra)
        self.assertEqual(len(nodes),6)
        children=[r for r in registry if r['parent_node']=='route:art_center']
        self.assertEqual(len(children),4)
        self.assertTrue(all(not r['route_selectable'] for r in children))

    def test_skate_duplicate_merge(self):
        nodes,registry,_=self.run_group([candidate('a','上海市滨江滑板公园'),candidate('b','滨江滑板公园',None)])
        skate=next(n for n in nodes if n['node_id']=='route:skate')
        self.assertEqual(set(skate['member_candidate_ids']),{'a','b'})
        self.assertEqual(len(nodes),6)

    def test_photography_bilingual_merge(self):
        nodes,registry,_=self.run_group([candidate('zh','上海摄影艺术中心',None),candidate('en','',name_en='Shanghai Center of Photography')])
        center=next(n for n in nodes if n['node_id']=='route:photography')
        self.assertEqual(len(center['member_candidate_ids']),2)
        self.assertEqual(len(center['sources']),2)

    def test_same_names_far_apart_are_not_forced_to_merge(self):
        nodes,_,_=self.run_group([candidate('a','滨江滑板公园'),candidate('b','上海市滨江滑板公园',(31.30,121.50))])
        self.assertFalse(any(n['node_id']=='route:skate' for n in nodes))
        self.assertTrue(all(n['identity']['identity_status']=='possible_duplicate' for n in nodes if not n.get('production_id')))

    def test_runway_bilingual_sources_one_node(self):
        nodes,_,_=self.run_group([candidate('a','跑道公园',None),candidate('b','徐汇跑道公园')])
        self.assertEqual(len(next(n for n in nodes if n['node_id']=='route:runway')['member_candidate_ids']),2)

    def test_tank_source_geometries_do_not_create_stops(self):
        p=self.repo.get_poi_by_id('p29')
        extra=[candidate('tank'+str(i),'油罐艺术中心',(p.coordinates[0]+i*.0001,p.coordinates[1])) for i in range(4)]
        nodes,registry,_=self.run_group(extra)
        self.assertEqual(len(nodes),5)
        tank=next(n for n in nodes if n['production_id']=='p29')
        self.assertEqual(len(tank['member_candidate_ids']),5)
        self.assertTrue(all(not r['route_selectable'] for r in registry))

    def test_production_not_admitted_as_new_and_known_content_retained(self):
        data=fixture_set(self.repo)
        before=rows_for(data)
        nodes,registry,_=RouteNodeConsolidator(self.repo).consolidate(data,before)
        rows=build_review(nodes,registry,before,self.repo)
        self.assertEqual(len(rows),5)
        self.assertTrue(all(r['admission_scope']=='production_audit_only' and not r['counts_as_new_stop'] for r in rows))
        for row in rows:
            self.assertEqual(row['production_snapshot']['visit_profile'],next(p for p in self.repo.get_raw_data()['pois'] if p['id']==row['production_match'])['visit_profile'])
            self.assertEqual(row['primary_role'],'anchor')

    def reviewed_fixture(self,name,extra_catalog):
        data=fixture_set(self.repo)+[candidate('test',name,(31.175,121.463))]
        rows=rows_for(data)
        _,catalog,_=semantic_fixtures()
        catalog['coordinates']['record_id']='amap:test'
        catalog.update(extra_catalog)
        rows[-1]['evidence_catalog']=catalog
        nodes,registry,_=RouteNodeConsolidator(self.repo).consolidate(data,rows)
        return next(r for r in build_review(nodes,registry,rows,self.repo) if r['admission_scope']=='new_route_node')

    def test_dome_one_node_two_visit_scopes(self):
        row=self.reviewed_fixture('西岸穹顶艺术中心（含北广场）',
            {'theatre':dict(value='amenity=theatre',field='category',group='osm',source_type='osm',record_id='osm:1')})
        self.assertEqual(row['node_id'],'route:dome')
        self.assertEqual(row['visit_profile']['full_visit']['standard'],60)
        self.assertIn('exterior/north plaza',row['visit_profile']['scope'])
        self.assertNotIn('parks',row['interest_tags'])

    def test_skate_social_tags_require_specific_community_evidence(self):
        row=self.reviewed_fixture('上海市滨江滑板公园',{
            'park':dict(value='风景名胜;公园广场;公园',field='category',group='map',source_type='amap',record_id='amap:test'),
            'community':dict(value='徐汇滨江滑板公园是本地滑板社群的重要聚集地。',field='snippet',group='public_space',source_type='government',record_id='gov:1')})
        self.assertIn('social_observation',row['experience_tags'])
        self.assertIn('public_life',row['culture_tags'])
        self.assertNotIn('quiet_walk',row['experience_tags'])
        self.assertNotIn('photogenic',row['experience_tags'])

    def test_runway_internal_water_does_not_force_waterfront(self):
        row=self.reviewed_fixture('徐汇跑道公园',{
            'history':dict(value='跑道公园以机场跑道为原型展现航空历史印迹，将原龙华机场跑道转变为新用途，把街道和公园组织成一个系统，穿插水系。',
                field='snippet',group='official',source_type='official',record_id='official:1')})
        self.assertIn('history',row['interest_tags'])
        self.assertIn('adaptive_reuse',row['experience_tags'])
        self.assertIn('street_scene',row['experience_tags'])
        self.assertNotIn('waterfront',row['interest_tags'])
        self.assertNotIn('riverside_walk',row['experience_tags'])


class RetryAndStrictnessTests(unittest.TestCase):
    def setUp(self):
        self.candidate,self.catalog,self.output=semantic_fixtures()
        self.taxonomy=baseline_repository().taxonomy

    def test_insufficient_evidence_zero_calls(self):
        client=MockLLMClient(responses=[self.output])
        result=TargetedSemanticRepair(client,self.taxonomy).run(self.candidate,self.catalog,reasons=['failed'],insufficient_evidence=True)
        self.assertEqual(len(client.calls),0)
        self.assertEqual(result['decision'],'needs_review')

    def test_successful_unaffected_candidate_is_not_retried(self):
        client=MockLLMClient(responses=[self.output])
        TargetedSemanticRepair(client,self.taxonomy).run(self.candidate,self.catalog,reasons=[])
        self.assertEqual(client.calls,[])

    def test_single_omittable_field_has_one_retry(self):
        bad=copy.deepcopy(self.output)
        bad['factual_fields']['opening_hours']=dict(text='开放的滨江公共广场',evidence_refs=['public'])
        client=MockLLMClient(responses=[bad,self.output])
        result=TargetedSemanticRepair(client,self.taxonomy).run(self.candidate,self.catalog,reasons=['failed'])
        self.assertEqual(len(client.calls),2)
        self.assertIsNotNone(result['semantic'])

    def test_unsupported_tags_do_not_trigger_repeated_generation(self):
        self.output['interest_tags'].append('parks')
        self.output['tag_evidence'].append(dict(group='interest_tags',tag='parks',evidence_refs=['public']))
        client=MockLLMClient(responses=[self.output,self.output,self.output])
        result=TargetedSemanticRepair(client,self.taxonomy).run(self.candidate,self.catalog,reasons=['tag_reconciliation_required'])
        self.assertEqual(len(client.calls),1)
        self.assertIsNone(result['semantic'])

    def test_schema_retry_bounded_at_two(self):
        client=MockLLMClient(responses=[{}, {},self.output])
        TargetedSemanticRepair(client,self.taxonomy).run(self.candidate,self.catalog,reasons=['merged'])
        self.assertEqual(len(client.calls),2)

    def test_validator_still_rejects_unknown_tags_and_invented_facts(self):
        for mutate in (lambda d:d['interest_tags'].append('sunset'),lambda d:d.update(coordinates=[0,0]),
                       lambda d:d['factual_fields'].update(former_functions=dict(text='古代机场',evidence_refs=['public']))):
            data=copy.deepcopy(self.output)
            mutate(data)
            with self.assertRaises(RequestValidationError):
                validate_semantic_enrichment(data,self.candidate,self.catalog,self.taxonomy)

    def test_evidence_dedup_keeps_support_links(self):
        catalog=copy.deepcopy(self.catalog)
        catalog['duplicate']=copy.deepcopy(catalog['public'])
        result=compact_evidence(catalog)
        self.assertIn('duplicate',result['public']['also_supported_by'])
        self.assertNotIn('coordinates',result)
        self.assertEqual(len(catalog),4)

    def test_history_failure_counts_not_cached_file_double_counts(self):
        rows=[dict(run=dict(attempts=[dict(status='failed',validation_feedback='parks unsupported by cited evidence'),
                                     dict(status='failed',validation_feedback='anchor requires high independent destination value'),
                                     dict(status='success')]))]
        stats=historical_failures(rows)
        self.assertEqual(stats['total_failed_attempts'],2)
        self.assertEqual(stats['primary_categories']['unsupported_tag_evidence_or_over_generation'],1)


if __name__=='__main__':unittest.main()

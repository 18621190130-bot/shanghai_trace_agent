import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from src.llm_client import DeepSeekLLMClient, MockLLMClient
from src.models import RequestValidationError
from src.poi_repository import POIRepository
from src.poi_pipeline.semantic.schema import FACTS, ROLES
from src.poi_pipeline.semantic.validation import validate_semantic_enrichment,validated_supported_subset
from src.poi_pipeline.semantic.preparation import prepare_candidates, geographic_context, duplicate_context
from src.poi_pipeline.semantic.enricher import POISemanticEnricher, SYSTEM_PROMPT
from src.poi_pipeline.semantic.admission import evaluate_citywalk_candidate, marginal_coverage_gain, coverage_preview


def fixtures():
    candidate=dict(candidate_id='fixture',name_zh='滨江测试广场',name_en='',aliases=[],entity_kind='public_space',
        coordinates=[31.175,121.463],coordinate_system='GCJ-02',boundary_status='inside_pilot',
        field_sources={'coordinates':'amap:1'},sources=[dict(source_type='amap',url='https://example.org/1',retrieved_at='fixture')])
    catalog={
        'identity':dict(value='滨江测试广场',field='name_zh',group='identity',record_id='amap:1',source_type='amap'),
        'public':dict(value='开放的滨江公共广场',field='snippet',group='public_space',record_id='official:1',source_type='official'),
        'coordinates':dict(value=dict(coordinates=[31.175,121.463],coordinate_system='GCJ-02'),field='coordinates',group='coordinates',record_id='amap:1',source_type='amap'),
    }
    output=dict(category='public_space',interest_tags=['waterfront'],experience_tags=['riverside_walk'],culture_tags=[],
        tag_evidence=[dict(group='interest_tags',tag='waterfront',evidence_refs=['public']),dict(group='experience_tags',tag='riverside_walk',evidence_refs=['public'])],
        category_evidence_refs=['public'],route_role=dict(primary='transition_stop',eligible=['transition_stop','supporting_stop'],confidence='medium',
            reason='短暂停留补充滨水体验，独立目的地价值有限。',independent_destination_value='low',route_connector_value='medium',
            alternatives_reason={r:'现有描述主要支持短暂停留，独立目的地证据有限。' for r in ROLES}),
        citywalk_value=dict(level='medium',reason='可提供滨水短暂停留。',evidence_refs=['public']),
        summary_draft=dict(text='开放的滨江公共广场',evidence_refs=['public']),culture_bridge_draft=None,
        visit_profile_proposal=dict(walk_stop=dict(quick=5,standard=10,deep=15),full_visit=None,time_basis='product_planning_estimate',scope='广场短暂停留'),
        semantic_confidence='medium',stability='stable',missing_information=['开放通行情况待确认'],
        factual_fields={f:None for f in FACTS},taxonomy_extension_candidate=[])
    return candidate,catalog,output


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.taxonomy=POIRepository().taxonomy
        self.candidate,self.catalog,self.output=fixtures()

    def validate(self, output=None):
        return validate_semantic_enrichment(output or self.output,self.candidate,self.catalog,self.taxonomy)

    def test_valid_output_and_missing_culture_allowed(self):
        result=self.validate()
        self.assertEqual(result['culture_tags'],[])
        self.assertEqual(result['coordinates'],self.candidate['coordinates'])
        self.assertFalse(result['verification']['production_imported'])

    def test_unknown_tag_rejected(self):
        self.output['interest_tags'].append('sunset')
        with self.assertRaises(RequestValidationError): self.validate()

    def test_llm_coordinates_rejected(self):
        self.output['coordinates']=[0,0]
        with self.assertRaises(RequestValidationError): self.validate()

    def test_inherited_coordinate_tampering_rejected(self):
        self.candidate['coordinates']=[31.18,121.47]
        with self.assertRaises(RequestValidationError): self.validate()

    def test_hallucinated_fact_rejected(self):
        self.output['factual_fields']['architect_names']=dict(text='某建筑师',evidence_refs=['public'])
        with self.assertRaises(RequestValidationError): self.validate()

    def test_wrong_fact_slot_rejected_even_with_real_quote(self):
        self.output['factual_fields']['opening_hours']=dict(text='开放的滨江公共广场',evidence_refs=['public'])
        with self.assertRaises(RequestValidationError): self.validate()

    def test_summary_cannot_hide_hallucinated_history(self):
        self.output['summary_draft']['text']='始建于1900年的旧工厂'
        with self.assertRaises(RequestValidationError): self.validate()

    def test_valid_official_fact_quote(self):
        self.catalog['history']=dict(value='该场所前身为旧厂房。',field='snippet',group='history',source_type='official',record_id='official:1')
        self.output['factual_fields']['former_functions']=dict(text='前身为旧厂房',evidence_refs=['history'])
        self.assertIsNotNone(self.validate()['factual_fields']['former_functions'])

    def test_unknown_reference_rejected(self):
        self.output['tag_evidence'][0]['evidence_refs']=['invented']
        with self.assertRaises(RequestValidationError): self.validate()

    def test_role_validation(self):
        for change in [dict(primary='landmark'),dict(primary='anchor'),dict(eligible=['anchor'])]:
            output=copy.deepcopy(self.output)
            output['route_role'].update(change)
            with self.assertRaises(RequestValidationError): self.validate(output)

    def test_duplicate_tags_removed(self):
        self.output['interest_tags'].append('waterfront')
        self.assertEqual(self.validate()['interest_tags'],['waterfront'])

    def test_coverage_gap_cannot_create_park_or_local_life(self):
        for tag in ('parks','local_life'):
            output=copy.deepcopy(self.output)
            output['interest_tags'].append(tag)
            output['tag_evidence'].append(dict(group='interest_tags',tag=tag,evidence_refs=['public']))
            with self.assertRaises(RequestValidationError): self.validate(output)
        self.assertIn('Coverage gaps are NOT evidence for assigning a tag',SYSTEM_PROMPT)

    def test_coverage_score_does_not_mutate_truth(self):
        before=copy.deepcopy(self.output)
        baseline=dict(coverage={g:dict(frequency={t:0 for t in tags}) for g,tags in self.taxonomy.items()})
        gain=marginal_coverage_gain(self.output,baseline)
        self.assertEqual(gain['score'],2)
        self.assertEqual(self.output,before)
        self.assertNotIn('parks',gain['newly_covered']['interest_tags'])

    def test_supported_subset_rejects_only_unsupported_known_tags_with_audit(self):
        self.output['interest_tags'].append('parks')
        self.output['tag_evidence'].append(dict(group='interest_tags',tag='parks',evidence_refs=['public']))
        result=validated_supported_subset(self.output,self.candidate,self.catalog,self.taxonomy)
        self.assertEqual(result['interest_tags'],['waterfront'])
        self.assertEqual(result['rejected_tag_proposals'][0]['tag'],'parks')
        self.assertIn('parks',self.output['interest_tags'])
        admission=evaluate_citywalk_candidate(self.candidate,result,dict(location_confidence='high'),dict(existing_production_ids=[],possible_candidate_duplicates=[]))
        self.assertEqual(admission['decision'],'review')

    def test_subset_cannot_rescue_unknown_tag_or_hallucinated_fact(self):
        bad=copy.deepcopy(self.output)
        bad['interest_tags'].append('sunset')
        with self.assertRaises(RequestValidationError):
            validated_supported_subset(bad,self.candidate,self.catalog,self.taxonomy)
        self.output['factual_fields']['opening_hours']=dict(text='09:00-18:00',evidence_refs=['public'])
        with self.assertRaises(RequestValidationError):
            validated_supported_subset(self.output,self.candidate,self.catalog,self.taxonomy)

    def test_generic_cafe_rejected(self):
        self.output['category']='generic_cafe'
        result=evaluate_citywalk_candidate(self.candidate,self.output,dict(location_confidence='high'),dict(existing_production_ids=[],possible_candidate_duplicates=[]))
        self.assertEqual(result['decision'],'reject')

    def test_missing_location_review_and_existing_duplicate_reject(self):
        self.candidate['coordinates']=None
        result=evaluate_citywalk_candidate(self.candidate,self.output,dict(location_confidence='low'),dict(existing_production_ids=[],possible_candidate_duplicates=[]))
        self.assertEqual(result['decision'],'review')
        result=evaluate_citywalk_candidate(self.candidate,self.output,dict(location_confidence='low'),dict(existing_production_ids=['p1'],possible_candidate_duplicates=[]))
        self.assertEqual(result['decision'],'reject')

    def test_visit_estimate_and_order(self):
        self.output['visit_profile_proposal']['time_basis']='official_average'
        with self.assertRaises(RequestValidationError): self.validate()
        self.output['visit_profile_proposal']['time_basis']='product_planning_estimate'
        self.output['visit_profile_proposal']['walk_stop']['quick']=30
        with self.assertRaises(RequestValidationError): self.validate()

    def test_user_grouping_keeps_components_and_original(self):
        first=copy.deepcopy(self.candidate)
        first.update(name_zh='西岸穹顶艺术中心',merged_source_records=[],issues=[])
        second=copy.deepcopy(first)
        second.update(candidate_id='plaza',name_zh='西岸穹顶北广场')
        candidates=[first,second]
        bundles=[dict(candidate_id=c['candidate_id'],evidence=dict(identity=[]),gaps=[],conflicts=[]) for c in candidates]
        prepared,_,manifest=prepare_candidates(candidates,bundles)
        self.assertEqual(len(prepared),1)
        self.assertEqual(len(prepared[0]['component_candidates']),2)
        self.assertEqual(prepared[0]['coordinates'],first['coordinates'])
        self.assertEqual(len(candidates),2)
        self.assertEqual(manifest[0]['coordinate_source_candidate'],'fixture')

    def test_mock_enrichment_retry_and_cache_no_live_calls(self):
        bad=copy.deepcopy(self.output)
        bad['interest_tags'].append('sunset')
        client=MockLLMClient(responses=[bad,self.output])
        with tempfile.TemporaryDirectory() as directory:
            enricher=POISemanticEnricher(client,self.taxonomy,directory,live=True,sleeper=lambda _:None)
            result,run=enricher.enrich(self.candidate,self.catalog,{})
            self.assertEqual(len(client.calls),2)
            self.assertEqual(run['api_calls_this_run'],2)
            offline=POISemanticEnricher(client,self.taxonomy,directory)
            replay,run=offline.enrich(self.candidate,self.catalog,{})
            self.assertTrue(run['cache_hit'])
            self.assertEqual(result,replay)
            self.assertEqual(len(client.calls),2)

    def test_non_museum_art_does_not_force_museum_visit(self):
        self.catalog['art']=dict(value='户外公共雕塑艺术',field='snippet',group='public_space',source_type='official',record_id='official:1')
        self.output['interest_tags'].append('art')
        self.output['tag_evidence'].append(dict(group='interest_tags',tag='art',evidence_refs=['art']))
        self.assertNotIn('museum_visit',self.validate()['experience_tags'])

    def test_all_tag_failures_reported_together_for_bounded_retry(self):
        self.output['interest_tags']+=['parks','local_life']
        self.output['tag_evidence'] += [dict(group='interest_tags',tag=t,evidence_refs=['public']) for t in ('parks','local_life')]
        with self.assertRaises(RequestValidationError) as raised:
            self.validate()
        self.assertIn('parks',str(raised.exception))
        self.assertIn('local_life',str(raised.exception))

    def test_coverage_preview_excludes_review_and_reject(self):
        baseline=dict(poi_count=5,coverage={g:dict(frequency={t:0 for t in tags}) for g,tags in self.taxonomy.items()})
        rows=[dict(candidate_id=str(i),decision=d,semantic=self.output,route_role=self.output['route_role']) for i,d in enumerate(('accept','review','reject'))]
        preview=coverage_preview(rows,baseline)
        self.assertEqual(preview['coverage']['interest_tags']['waterfront']['proposed_after'],1)
        self.assertEqual(preview['proposed_additions'],1)

    def test_shared_provider_budget_override_and_usage(self):
        response=io.BytesIO(json.dumps(dict(choices=[dict(finish_reason='stop',message=dict(content='{}'))],usage=dict(total_tokens=20))).encode())
        with patch.dict('os.environ',DEEPSEEK_API_KEY='fake-test-key'),patch('urllib.request.urlopen',return_value=response) as network:
            client=DeepSeekLLMClient(max_tokens=3600)
            client.structured_parse(system_prompt='test',user_text='test',schema={})
        self.assertEqual(json.loads(network.call_args.args[0].data)['max_tokens'],3600)
        self.assertEqual(client.last_response_metadata['usage']['total_tokens'],20)


if __name__=='__main__': unittest.main()

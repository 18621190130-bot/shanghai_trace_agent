"""Current production routes + fixture NLU, without live APIs."""
import json
import unittest
from pathlib import Path
from tests import test_web_frontend_api as web_fixture
intent=web_fixture.intent
from src.llm_client import MockLLMClient
from src.trip_action_fixtures import action, utterance

class FeedbackTests(unittest.TestCase):
    setUp=web_fixture.WebAdapterTests.setUp
    def start(self, **kw):
        r=self.app.generate(self.session,intent(**kw))
        self.assertEqual(r['entry']['status'],'success',r['entry']['status'])
        return self.app.action(self.session,dict(action='start',revision=r['trip']['state_revision']))['trip']
    def turn_fixture(self,text,*actions):
        self.app.llm=MockLLMClient(responses=[utterance(*actions)])
        trip=self.app.current_trip(self.session)
        return self.app.turn(self.session,dict(text=text,revision=trip['state_revision']))
    def test_actual_english_shorten_three_routes(self):
        evidence=[]
        for zone,tags in [('wukang_fuxing_xujiahui',['architecture','local_life']),('west_bund',['architecture','waterfront']),('old_city_xintiandi_bund',['architecture','history'])]:
            _,self.session=self.app.session()
            if zone not in self.repo.zone_order:zone=self.repo.zone_order[1]
            before=self.start(preferred_zone=zone,interest_tags=tags)
            r=self.turn_fixture("I'm tired. Cut the route for me.",action('SHORTEN_ROUTE',reduction_goal='easier'))
            f=r['turn']['change_summary'];self.assertEqual(f['execution_status'],'APPLIED',r['turn'])
            self.assertLess(f['after_metrics']['duration_minutes'],f['before_metrics']['duration_minutes'])
            self.assertLess(f['after_metrics']['stops'],f['before_metrics']['stops'])
            self.assertEqual(r['trip']['original_route'],before['original_route']);evidence.append(f)
        Path('examples/replan_feedback/shorten_real_routes.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    def test_add_two_real_engine_and_history(self):
        before=self.start()
        # Establish exactly five accepted stops without changing the default route cap.
        if len(before['active_route']['ordered_pois'])<5:
            self.turn_fixture('Add places',action('ADD_MATCHING_STOPS',requested_count=5-len(before['active_route']['ordered_pois'])))
        r=self.turn_fixture('Add another two places to the route.',action('ADD_MATCHING_STOPS',requested_count=2))
        f=r['turn']['change_summary'];self.assertEqual(f['execution_status'],'APPLIED')
        self.assertEqual((f['before_metrics']['stops'],f['after_metrics']['stops']),(5,7))
        self.assertEqual(len(f['added_ids']),2);self.assertFalse(f['removed_ids'])
        self.assertTrue(self.app.bootstrap(self.session)['trip']['change_history'])
        Path('examples/replan_feedback/add_two_real_route.json').write_text(json.dumps(f,indent=2),encoding='utf-8')
    def test_must_go_protected_no_commit(self):
        self.start(mode='places_in_mind',available_minutes=None,must_go_poi_ids=['p28','p5'],preferred_zone='west_bund',interest_tags=[])
        before=self.app.current_trip(self.session)
        r=self.turn_fixture("I'm tired. Cut the route for me.",action('SHORTEN_ROUTE',reduction_goal='easier'))
        self.assertEqual(r['turn']['change_summary']['execution_status'],'NO_CHANGE')
        self.assertEqual(before['state_revision'],r['trip']['state_revision'])
    def test_partial_count_and_soft_budget(self):
        self.start()
        self.turn_fixture('Prefer 15 minutes',action('SET_TIME_TARGET',time_value_minutes=15))
        r=self.turn_fixture('Add twenty places',action('ADD_MATCHING_STOPS',requested_count=20))
        f=r['turn']['change_summary'];self.assertEqual(f['execution_status'],'PARTIALLY_APPLIED');self.assertGreater(f['actual_added_count'],0);self.assertTrue(f['warnings'])
        r=self.turn_fixture('Add another two places to the route.',action('ADD_MATCHING_STOPS',requested_count=2))
        self.assertEqual(r['turn']['change_summary']['execution_status'],'NO_CHANGE')
    def test_less_walking_and_ambiguous_no_write(self):
        self.start()
        r=self.turn_fixture('I want less walking',action('SHORTEN_ROUTE',reduction_goal='walking'))
        f=r['turn']['change_summary'];self.assertLess(f['after_metrics']['walking_km'],f['before_metrics']['walking_km'])
        before=r['trip']['state_revision']
        self.app.llm=MockLLMClient(responses=[utterance(action('UNSUPPORTED'),needs_clarification=True,clarification_reason='unclear')])
        r=self.app.turn(self.session,dict(text='Change it somehow',revision=before))
        self.assertEqual(r['turn']['change_summary']['execution_status'],'NEEDS_CLARIFICATION');self.assertEqual(before,r['trip']['state_revision'])
    def test_preferences_progress_and_count(self):
        trip=self.start()
        pid=trip['current_poi_id']
        self.app.action(self.session,dict(action='complete',poi_id=pid,revision=trip['state_revision']))
        r=self.turn_fixture('Add two cultural places',action('ADD_MATCHING_STOPS',requested_count=2,preference_tags=['history']))
        self.assertNotIn(pid,r['turn']['change_summary']['added_ids'])
        self.assertIn(pid,r['trip']['visited_poi_ids'])
        for added in r['turn']['change_summary']['added_ids']:
            p=self.repo.get_poi_by_id(added)
            self.assertIn('history',p.interest_tags+p.experience_tags+p.culture_tags)
        self.assertEqual(r['trip']['current_intent']['interest_tags'],trip['current_intent']['interest_tags'])
    def test_hard_hour_and_ambiguous_museum(self):
        self.start(mode='places_in_mind',available_minutes=None,must_go_poi_ids=['p28','p5'],preferred_zone='west_bund',interest_tags=[])
        before=self.app.current_trip(self.session)
        r=self.turn_fixture('Keep the museum',action('ADD_MUST_GO',target_mentions=['the museum']))
        self.assertEqual(r['turn']['change_summary']['execution_status'],'NEEDS_CLARIFICATION')
        self.assertEqual(before['state_revision'],r['trip']['state_revision'])
        self.app.conversations.clear(before['trip_id'])
        r=self.turn_fixture('I only have one hour left',action('SET_HARD_TIME_LIMIT',time_value_minutes=60))
        self.assertIn(r['turn']['change_summary']['execution_status'],('APPLIED','FAILED'))
        self.assertEqual(set(before['current_intent']['must_go_poi_ids']),set(r['trip']['current_intent']['must_go_poi_ids']))
    def test_stale_and_history_survives_progress(self):
        before=self.start()
        r=self.turn_fixture('Add two stops',action('ADD_MATCHING_STOPS',requested_count=2))
        with self.assertRaisesRegex(ValueError,'stale_state_conflict'):
            self.app.turn(self.session,dict(kind='SET_PACE',pace='quick',revision=before['state_revision']))
        after=self.app.action(self.session,dict(action='complete',poi_id=r['trip']['current_poi_id'],revision=r['trip']['state_revision']))
        self.assertEqual(len(after['trip']['change_history']),1)
        self.assertEqual(before['original_route'],after['trip']['original_route'])
    def test_places_without_duration(self):
        r=self.app.generate(self.session,intent('places_in_mind',available_minutes=None,interest_tags=[],must_go_poi_ids=['p28','p5'],preferred_zone='west_bund'))
        self.assertEqual(r['entry']['status'],'success')
        self.assertEqual(set(s['poi_id'] for s in r['trip']['active_route']['ordered_pois']),{'p28','p5'})
    def test_surprise_park_first(self):
        parks=[p for p in self.repo.get_all_pois() if p.poi_type=='park']
        self.assertTrue(parks)
        for p in parks:
            _,self.session=self.app.session()
            r=self.app.generate(self.session,intent('surprise_me',available_minutes=240,interest_tags=[],preferred_zone=p.zone_id,start_poi_id=p.id))
            self.assertIn(r['entry']['status'],('success','needs_route_quality_clarification'),(p.id,r['entry']['status']))
            self.assertEqual(r['entry']['route_plan']['ordered_pois'][0]['poi_id'],p.id)

if __name__=='__main__':unittest.main()

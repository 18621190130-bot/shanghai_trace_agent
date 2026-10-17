from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import unittest
from unittest.mock import patch

from src import POIRepository, RouteEntryService, RouteIntent, RouteMode, RouteRequest, RouteEngine
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from src.models import RequestValidationError
from .helpers import subset, write_repository

WEST = "I have three hours for a city walk in the west bund and I'm more interested in art and natural scenery and I don't like museums."


class UnifiedPatchTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()

    def parse(self, text, **fields):
        service = RouteEntryService(self.repo, MockLLMClient(responses=[candidate(**fields)]))
        return service.parse_plan(text)

    def service_with_stops(self, count):
        raw = self.repo.get_raw_data()
        ids = ('p2', 'p11', 'p12')[:count]
        # A zero-match catalog still contains a real unrelated venue.
        points = [p for p in raw['pois'] if p['id'] in (ids or ('p28',))]
        return RouteEntryService(write_repository(self, subset(raw, points)))

    def intent(self):
        return RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, interest_tags=['local_life'])

    def test_one_exact_concept_needs_one_tag(self):
        intent = self.parse('Two hours for literature.', available_minutes=120, interest_tags=['literature'])
        self.assertEqual(intent.semantic_concepts, [dict(concept='literature', primary='literature', secondary=[])])

    def test_wide_scenery_concept_maps_two_tags(self):
        intent = self.parse(WEST, available_minutes=180, interest_tags=['art', 'parks'],
                            preferred_zone='west_bund', avoid_tags=['museum_visit'])
        self.assertIn('waterfront', intent.interest_tags)
        scenery = next(c for c in intent.semantic_concepts if c['concept'] == 'natural scenery')
        self.assertEqual(scenery['primary'], 'waterfront')
        self.assertEqual(scenery['secondary'], ['parks'])
        self.assertEqual(intent.avoid_tags, ['museum_visit'])

    def test_river_views_does_not_automatically_mean_parks(self):
        intent = self.parse('Three hours for river views.', available_minutes=180)
        self.assertEqual(intent.interest_tags, ['waterfront'])

    def test_genuinely_multidimensional_concept_has_three_tags(self):
        intent = self.parse('Three hours for old Shanghai atmosphere.', available_minutes=180)
        self.assertEqual(intent.interest_tags, ['history', 'architecture', 'local_life'])
        self.assertEqual(len(intent.semantic_concepts[0]['secondary']), 2)

    def test_art_alone_does_not_expand_to_unstated_interests(self):
        intent = self.parse('I want art for two hours.', available_minutes=120, interest_tags=['art'])
        self.assertEqual(intent.interest_tags, ['art'])
        self.assertEqual(intent.semantic_concepts[0]['secondary'], [])

    def test_negative_surface_is_not_positively_expanded(self):
        intent = self.parse("I dislike river views but love art for two hours. I don't like museums.",
                            available_minutes=120, interest_tags=['art'], avoid_tags=['museum_visit'])
        self.assertEqual(intent.interest_tags, ['art'])
        self.assertEqual(intent.avoid_tags, ['museum_visit'])

    def test_unknown_tags_and_more_than_three_per_concept_are_rejected(self):
        for concepts in ([dict(concept='scenery', primary='made_up', secondary=[])],
                         [dict(concept='scenery', primary='waterfront', secondary=['parks', 'history', 'architecture'])]):
            payload = candidate(available_minutes=180, semantic_concepts=concepts)
            client = MockLLMClient(fixtures={'scenery': payload})
            with self.assertRaises(RequestValidationError):
                RouteEntryService(self.repo, client).parse_plan('scenery')

    def test_provider_concept_expansion_handles_other_grounded_positive_phrases(self):
        intent = self.parse('Two hours exploring converted factories.', available_minutes=120,
            semantic_concepts=[dict(concept='converted factories', primary='industrial_heritage', secondary=['adaptive_reuse'])])
        self.assertIn('industrial_heritage', intent.interest_tags)
        self.assertIn('adaptive_reuse', intent.experience_tags)

    def test_zero_stop_requires_clarification_without_increase_time_advice(self):
        service = self.service_with_stops(0)
        intent = self.intent()
        intent.preferred_zone = 'west_bund'
        intent.avoid_tags = ['museum_visit']
        result = service.generate(intent)
        self.assertEqual(result.status, 'needs_route_quality_clarification')
        self.assertEqual(result.route_quality.reasons, ['no_eligible_candidates'])
        self.assertFalse(result.route_quality.minimum_viable)
        self.assertFalse(any('Increase' in s for s in result.route_plan.relaxation_suggestions))

    def test_one_and_two_stops_require_clarification_even_with_high_utilization(self):
        for count in (1, 2):
            service = self.service_with_stops(count)
            intent = self.intent()
            intent.available_minutes = 90
            result = service.generate(intent)
            self.assertEqual(result.status, 'needs_route_quality_clarification')
            self.assertEqual(result.route_quality.actual_stops, count)

    def test_three_stops_pass_even_if_preferred_richness_unmet(self):
        result = self.service_with_stops(3).generate(self.intent())
        self.assertEqual(result.status, 'success')
        self.assertTrue(result.route_quality.minimum_viable)
        self.assertFalse(result.route_plan.richness_target_met)

    def test_surprise_partial_route_fails_minimum(self):
        service = RouteEntryService(self.repo)
        intent = RouteIntent(RouteMode.SURPRISE_ME, start_location_text='West Bund', available_minutes=180,
                             preferred_zone='west_bund', avoid_tags=['museum_visit'])
        result = service.generate(intent)
        self.assertEqual(result.status, 'needs_route_quality_clarification')
        self.assertFalse(result.route_quality.minimum_viable)

    def test_surprise_answer_preserves_merged_theme_and_replans_once(self):
        service = RouteEntryService(self.repo)
        intent = RouteIntent(RouteMode.SURPRISE_ME, start_location_text='West Bund', available_minutes=180,
                             preferred_zone='west_bund', avoid_tags=['museum_visit'])
        pending = service.generate(intent)
        choice = next(o.value for o in pending.route_quality.options if o.value not in ('strict', 'broaden_area'))
        with patch.object(service.engine, 'generate_route', wraps=service.engine.generate_route) as planner:
            final = service.answer_route_quality_clarification(pending, choice)
        self.assertEqual(planner.call_count, 1)
        self.assertIn(choice, final.intent.interest_tags)
        self.assertTrue(set(pending.intent.interest_tags).issubset(final.intent.interest_tags))
        self.assertEqual(final.intent.avoid_tags, ['museum_visit'])
        self.assertTrue(final.route_quality.clarification_applied)
        self.assertEqual(final.route_quality.options, [])

    def test_places_two_explicit_stops_are_respected(self):
        service = self.service_with_stops(2)
        intent = RouteIntent(RouteMode.PLACES_IN_MIND, available_minutes=180, must_go_poi_ids=['p2', 'p11'])
        result = service.generate(intent)
        self.assertEqual(result.status, 'success')
        self.assertEqual(len(result.route_plan.ordered_pois), 2)
        self.assertIsNone(result.route_quality)

    def test_zero_candidates_then_theme_merge_replans_once(self):
        service = RouteEntryService(self.repo)
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone='west_bund',
                             interest_tags=['art'], avoid_tags=['museum_visit'])
        pending = service.generate(intent)
        self.assertEqual(pending.route_quality.actual_stops, 0)
        self.assertIn('waterfront', [o.value for o in pending.route_quality.options])
        with patch.object(service.engine, 'generate_route', wraps=service.engine.generate_route) as planner:
            final = service.answer_route_quality_clarification(pending, 'waterfront')
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(final.intent.interest_tags, ['art', 'waterfront'])
        self.assertEqual(final.intent.avoid_tags, ['museum_visit'])
        self.assertEqual(final.status, 'insufficient_route')
        self.assertEqual(final.route_quality.actual_stops, 1)
        with self.assertRaises(RequestValidationError):
            service.answer_route_quality_clarification(final, 'waterfront')

    def test_keep_current_preferences_returns_insufficient_route(self):
        service = self.service_with_stops(2)
        pending = service.generate(self.intent())
        final = service.answer_route_quality_clarification(pending, 'strict')
        self.assertEqual(final.status, 'insufficient_route')
        self.assertEqual(final.intent.to_dict(), pending.intent.to_dict())
        self.assertEqual(len(final.route_plan.ordered_pois), 2)
        self.assertFalse(any('Increase' in s for s in final.route_plan.relaxation_suggestions))

    def test_area_broadening_is_explicit_and_preserves_all_other_fields(self):
        service = RouteEntryService(self.repo)
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone='west_bund',
            interest_tags=['local_life'], experience_tags=['local_atmosphere'], avoid_tags=['museum_visit'])
        pending = service.generate(intent)
        self.assertEqual(pending.intent.preferred_zone, 'west_bund')
        final = service.answer_route_quality_clarification(pending, 'broaden_area')
        self.assertIsNone(final.intent.preferred_zone)
        self.assertEqual(final.intent.interest_tags, intent.interest_tags)
        self.assertEqual(final.intent.avoid_tags, intent.avoid_tags)
        self.assertEqual(final.status, 'success')

    def test_minimum_does_not_force_low_quality_filler(self):
        result = RouteEntryService(self.repo).generate(self.intent())
        self.assertEqual(len(result.route_plan.ordered_pois), 3)
        self.assertNotIn('p33', [p.poi_id for p in result.route_plan.ordered_pois])

    def test_options_have_actual_zone_support_and_respect_avoid(self):
        service = RouteEntryService(self.repo)
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone='west_bund',
                             interest_tags=['art'], avoid_tags=['museum_visit'])
        pending = service.generate(intent)
        from src.route_quality import eligible_catalog
        points = eligible_catalog(intent, self.repo, 'west_bund')
        for option in pending.route_quality.options:
            if option.value not in ('strict', 'broaden_area'):
                self.assertTrue(any(option.value in p.interest_tags for p in points))
                self.assertNotIn(option.value, intent.avoid_tags)

    def test_genuine_budget_failure_keeps_budget_advice(self):
        plan = RouteEngine(self.repo).generate_route(RouteRequest(1, interest_tags=['local_life']))
        self.assertEqual(plan.status, 'infeasible')
        self.assertTrue(any('Increase' in s for s in plan.relaxation_suggestions))

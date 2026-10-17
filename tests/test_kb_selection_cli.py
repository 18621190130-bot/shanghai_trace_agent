"""Offline manual-entry checks; live chat provider is replaced by a mock."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.demos import chat_demo
from tools.demos import route_entry_demo
from src.kb_selection import resolve_poi_repository, kb_summary, CANDIDATE_PATH
from src.poi_repository import POIRepository, DEFAULT_DATA_PATH
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from .helpers import subset, write_repository


class KBSelectionCLITests(unittest.TestCase):
    def call(self, args, entry=route_entry_demo.main, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = entry(args, **kwargs)
        return code, json.loads(output.getvalue())

    def test_no_kb_argument_uses_production(self):
        self.assertEqual(resolve_poi_repository().path, DEFAULT_DATA_PATH)
        _, result = self.call(['--mode', 'surprise_me', '--start', 'West Bund', '--minutes', '180', '--json'])
        self.assertEqual(result['POI KB'], 'production')
        self.assertEqual(result['POI Count'], len(POIRepository().get_all_pois()))

    def test_explicit_production_and_default_same_route(self):
        args = ['--mode', 'surprise_me', '--start', 'West Bund', '--minutes', '180', '--seed', '42', '--json']
        self.assertEqual(resolve_poi_repository('production').path, DEFAULT_DATA_PATH)
        self.assertEqual(self.call(args), self.call(['--kb', 'production', *args]))

    def test_candidate_loads_explicit_file_and_actual_counts(self):
        repo = resolve_poi_repository('phase2_5_candidate')
        self.assertEqual(repo.path, CANDIDATE_PATH)
        raw = json.loads(CANDIDATE_PATH.read_text(encoding='utf-8'))
        info = kb_summary('phase2_5_candidate', repo)
        self.assertEqual(info['POI Count'], len(raw['pois']))
        self.assertEqual(info['West Bund Route Nodes'], sum(p['walk_zone']['id'] == 'west_bund'
            and p.get('counts_as_route_stop', True) for p in raw['pois']))

    def test_counts_change_with_actual_fixture_file_not_hardcoded(self):
        raw = POIRepository(CANDIDATE_PATH).get_raw_data()
        raw = subset(raw, [p for p in raw['pois'] if p['id'] != 'p43'])
        fixture = write_repository(self, raw)
        with patch('src.kb_selection.CANDIDATE_PATH', fixture.path):
            repo = resolve_poi_repository('phase2_5_candidate')
            info = kb_summary('phase2_5_candidate', repo)
        self.assertEqual(info['POI Count'], len(raw['pois']))
        self.assertEqual(info['West Bund Route Nodes'], len(repo.get_pois_by_zone('west_bund')))
        self.assertNotEqual(info['POI Count'], len(POIRepository(CANDIDATE_PATH).get_all_pois()))

    def test_chat_and_route_entry_share_selection_and_places_flow(self):
        self.assertIs(chat_demo.main, route_entry_demo.main)
        args = ['--kb', 'phase2_5_candidate', '--mode', 'places_in_mind',
                '--places', '徐汇滨江海事塔广场;北票码头塔吊', '--minutes', '120', '--json']
        with patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=MockLLMClient()) as provider:
            chat = self.call(args, entry=chat_demo.main, live=True)
        self.assertEqual(chat, self.call(args))
        self.assertEqual(chat[0], 0)
        self.assertEqual(chat[1]['status'], 'success')
        self.assertEqual(set(chat[1]['intent']['must_go_poi_ids']), {'p42', 'p43'})
        self.assertEqual({s['poi_id'] for s in chat[1]['route_plan']['ordered_pois']}, {'p42', 'p43'})
        self.assertFalse(chat[1]['route_plan']['composition_diagnostics']['enabled'])

    def test_surprise_candidate_uses_candidate_composition(self):
        code, result = self.call(['--kb', 'phase2_5_candidate', '--mode', 'surprise_me',
            '--start', 'West Bund', '--minutes', '180', '--seed', '42', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['POI Count'], len(POIRepository(CANDIDATE_PATH).get_all_pois()))
        self.assertTrue(result['route_plan']['composition_diagnostics']['enabled'])
        self.assertTrue(result['route_plan']['composition_diagnostics']['route_composition_passed'])

    def test_chat_plan_mock_provider_then_candidate_filtering(self):
        text = 'Test explicit candidate art without museums'
        mock = MockLLMClient(fixtures={text: candidate(available_minutes=180, preferred_zone='west_bund',
            interest_tags=['art'], avoid_tags=['museum_visit'])})
        with patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=mock), \
                patch('builtins.input', side_effect=AssertionError('JSON must not read input')):
            code, result = self.call(['--kb', 'phase2_5_candidate', '--mode', 'plan_for_me', '--text', text, '--json'],
                                     entry=chat_demo.main, live=True)
        self.assertEqual(code, 1)  # Existing composition failure is correctly exposed, not concealed.
        self.assertEqual(result['status'], 'composition_failure')
        self.assertEqual(len(result['route_plan']['ordered_pois']), 3)
        self.assertTrue(result['route_plan']['composition_diagnostics']['minimum_stop_count_passed'])
        self.assertTrue(all(s['poi_id'] in ('p36','p37','p41') for s in result['route_plan']['ordered_pois']))
        self.assertEqual(len(mock.calls), 1)

    def test_plain_output_starts_with_kb_information_and_diagnostics(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = route_entry_demo.main(['--kb', 'phase2_5_candidate', '--mode', 'places_in_mind',
                '--places', '徐汇滨江海事塔广场;北票码头塔吊', '--minutes', '120'])
        summary = kb_summary('phase2_5_candidate', POIRepository(CANDIDATE_PATH))
        self.assertEqual(code, 0)
        self.assertTrue(output.getvalue().startswith('POI KB: phase2_5_candidate\n'))
        self.assertIn(f"POI Count: {summary['POI Count']}", output.getvalue())
        self.assertIn(f"West Bund Route Nodes: {summary['West Bund Route Nodes']}", output.getvalue())
        self.assertIn('Route Composition Enabled: False', output.getvalue())

    def test_candidate_list_places_header_and_new_names(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(route_entry_demo.main(['--kb', 'phase2_5_candidate', '--list-places']), 0)
        self.assertIn('POI KB: phase2_5_candidate', output.getvalue())
        self.assertIn('徐汇滨江海事塔广场', output.getvalue())
        self.assertIn('北票码头塔吊', output.getvalue())

    def test_production_places_never_resolves_an_unknown_name(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            code = route_entry_demo.main(['--mode', 'places_in_mind', '--places', 'nonexistent-promotion-test-place', '--minutes', '120', '--json'])
        self.assertEqual(code, 2)
        error = json.loads(errors.getvalue())
        self.assertEqual(error['POI KB'], 'production')
        self.assertEqual(error['status'], 'validation_error')

    def test_invalid_or_missing_candidate_never_falls_back(self):
        with self.assertRaises(ValueError):
            resolve_poi_repository('auto')
        from src.models import DataValidationError
        with patch('src.kb_selection.CANDIDATE_PATH', Path('missing_candidate_kb.json')):
            with self.assertRaises(DataValidationError):
                resolve_poi_repository('phase2_5_candidate')

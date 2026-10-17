"""Phase 3B_1 offline contracts; no real network or real credentials."""
import copy
import io
import json
import os
import socket
import traceback
import unittest
import urllib.error
from dataclasses import asdict
from unittest.mock import Mock, patch

from src import POIRepository, RouteEngine, RouteRequest, RouteEntryService
from src.intent_models import RouteIntent, RouteMode
from src.providers.amap import AmapClient, AmapWalkingProvider
from src.providers.base import (ExternalProviderError, ProviderQuotaError, ProviderResponseError,
                               ProviderTimeoutError, ProviderUnavailableError)
from src.walking_models import Location
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.trip_replanning import ReplanningCoordinator
from src.trip_state import TripState, TripStateDelta
from src.trip_store import InMemoryTripStore, TripService, StaleStateConflict
from src.route_mutation import RouteMutationService
from tools.demos.trip_demo import load_fixture

A = Location(31.175, 121.463, 'GCJ02')
B = Location(31.176, 121.464, 'GCJ-02')
C = Location(31.177, 121.465, 'GCJ02')
D = Location(31.178, 121.466, 'GCJ02')


def payload():
    return {'status': '1', 'infocode': '10000', 'route': {'paths': [{
        'distance': '300', 'duration': '240', 'steps': [
            {'instruction': '沿龙腾大道步行', 'road': '龙腾大道', 'distance': '100', 'duration': '80',
             'polyline': '121.463,31.175;121.4635,31.1755'},
            {'instruction': '继续步行', 'distance': '200', 'duration': '160',
             'polyline': '121.4635,31.1755;121.464,31.176'}]}]}}


def provider_for(data=None):
    opener = Mock(side_effect=lambda *a, **k: io.BytesIO(json.dumps(data if data is not None else payload()).encode()))
    with patch.dict(os.environ, AMAP_WEB_SERVICE_KEY='unit-placeholder'):
        provider = AmapWalkingProvider(AmapClient(opener=opener, min_interval_s=0))
    return provider, opener


def tiny_route(locations=(A, B, C, D)):
    return dict(status='success', request={}, total_estimated_distance_km=.9,
                total_estimated_walking_minutes=12,
                ordered_pois=[dict(poi_id=str(i), name_en=str(i), coordinate_system=p.coordinate_system,
                                   estimated_coordinates=[p.lat, p.lng],
                                   estimated_distance_from_previous_stop_km=0 if i == 0 else .3,
                                   estimated_walking_minutes=0 if i == 0 else 4) for i, p in enumerate(locations)])


class ProviderTests(unittest.TestCase):
    def test_single_leg_multiple_steps_and_polyline(self):
        provider, network = provider_for()
        result = provider.get_walking_route(A, B)
        self.assertEqual((result.distance_m, result.duration_s), (300, 240))
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(len(result.polyline), 3)
        self.assertEqual(result.polyline[0], (121.463, 31.175))
        self.assertIsNone(result.steps[1].road)
        self.assertEqual(result.provider, 'amap')
        self.assertIn('+00:00', result.fetched_at)
        request = network.call_args.args[0]
        self.assertIn('/v3/direction/walking?', request.full_url)
        self.assertIn('origin=121.463000%2C31.175000', request.full_url)

    def test_optional_fields_missing_not_invented(self):
        data = payload()
        for item in data['route']['paths'][0]['steps']:
            for field in ('instruction', 'road', 'distance', 'duration'):
                item.pop(field, None)
        provider, _ = provider_for(data)
        step = provider.get_walking_route(A, B).steps[0]
        self.assertEqual((step.instruction, step.road, step.distance_m, step.duration_s), (None, None, None, None))

    def test_missing_required_data_rejected(self):
        examples = [dict(status='1'), dict(status='1', route={}), dict(status='1', route={'paths': []})]
        for field in ('distance', 'duration', 'steps'):
            data = payload();data['route']['paths'][0].pop(field)
            examples.append(data)
        for value in ('nan', '-1', True, [], None):
            data = payload();data['route']['paths'][0]['distance'] = value
            examples.append(data)
        for data in examples:
            with self.subTest(data=data), self.assertRaises(ProviderResponseError):
                provider_for(data)[0].get_walking_route(A, B)

    def test_invalid_steps_and_geometry_rejected(self):
        for value in ('', [], None, 'NaN,31', '181,31', '121,91', '121,31,5', 'invalid'):
            data = payload();data['route']['paths'][0]['steps'][0]['polyline'] = value
            with self.subTest(value=value), self.assertRaises(ProviderResponseError):
                provider_for(data)[0].get_walking_route(A, B)
        for steps in ([], {}, None, [None]):
            data = payload();data['route']['paths'][0]['steps'] = steps
            with self.subTest(steps=steps), self.assertRaises(ProviderResponseError):
                provider_for(data)[0].get_walking_route(A, B)

    def test_gcj_passes_through_without_conversion(self):
        provider, network = provider_for()
        self.assertIs(provider.normalize_location_for_amap(A), A)
        network.assert_not_called()

    def test_wgs_conversion_then_route(self):
        provider, network = provider_for()
        network.side_effect = [io.BytesIO(b'{"status":"1","locations":"121.463,31.175"}'),
                               io.BytesIO(json.dumps(payload()).encode())]
        result = provider.get_walking_route(Location(31.17, 121.46, 'WGS84'), B)
        self.assertEqual(result.origin, A)
        self.assertEqual(network.call_count, 2)
        self.assertIn('coordsys=gps', network.call_args_list[0].args[0].full_url)
        self.assertIn('origin=121.463000%2C31.175000', network.call_args_list[1].args[0].full_url)

    def test_invalid_conversion_is_safe(self):
        provider, _ = provider_for({'status': '1', 'locations': 'bad'})
        with self.assertRaises(ProviderResponseError):
            provider.get_walking_route(Location(31, 121, 'WGS84'), B)

    def test_coordinate_validation(self):
        for lat, lng, system in ((91, 121, 'GCJ02'), (31, 181, 'GCJ02'), (True, 121, 'GCJ02'),
                                 (float('nan'), 121, 'WGS84'), (31, 121, 'unknown')):
            with self.subTest(system=system), self.assertRaises(ValueError):Location(lat, lng, system)

    def test_transport_errors_classified_and_redacted(self):
        cases = [(socket.timeout('unit-placeholder'), ProviderTimeoutError),
                 (urllib.error.URLError('unit-placeholder'), ProviderUnavailableError),
                 (urllib.error.URLError(TimeoutError()), ProviderTimeoutError),
                 (urllib.error.HTTPError('https://example.invalid/?key=unit-placeholder', 500, 'bad', {}, None), ProviderUnavailableError),
                 (urllib.error.HTTPError('https://example.invalid/?key=unit-placeholder', 429, 'bad', {}, None), ProviderQuotaError)]
        for error, expected in cases:
            provider, network = provider_for();network.side_effect = error
            try:provider.get_walking_route(A, B)
            except expected as exc:
                self.assertNotIn('unit-placeholder', ''.join(traceback.format_exception(exc)))
                self.assertIsNone(exc.__context__)
            else:self.fail('Expected classified error')

    def test_json_and_provider_status_failures(self):
        for body, expected in [(b'not json', ProviderResponseError), (b'[]', ProviderResponseError),
                               (b'{"status":"0","infocode":"10003"}', ProviderQuotaError),
                               (b'{"status":"0","info":"unit-placeholder"}', ProviderUnavailableError),
                               (b'{"route":{}}', ProviderUnavailableError)]:
            provider, network = provider_for();network.side_effect = lambda *a, **k: io.BytesIO(body)
            with self.subTest(body=body), self.assertRaises(expected):provider.get_walking_route(A, B)

    def test_missing_key_does_not_make_request(self):
        with patch.dict(os.environ, AMAP_WEB_SERVICE_KEY=''):
            network = Mock();client = AmapClient(opener=network)
        with self.assertRaises(ProviderUnavailableError):client.get('/v3/direction/walking', {})
        network.assert_not_called()

    def test_response_and_timeout_bounds(self):
        for value in (0, -1, float('inf')):
            with self.assertRaises(ValueError):AmapClient(timeout_s=value)
        provider, network = provider_for()
        provider.client.MAX_RESPONSE_BYTES = 3
        with self.assertRaises(ProviderResponseError):provider.get_walking_route(A, B)

    def test_provider_text_cannot_echo_key(self):
        data = payload();data['route']['paths'][0]['steps'][0]['instruction'] = 'unit-placeholder'
        result = provider_for(data)[0].get_walking_route(A, B)
        self.assertNotIn('unit-placeholder', json.dumps(asdict(result)))

    def test_request_pacing_with_fake_clock(self):
        now = [0.0];waits = []
        def sleep(delay):
            waits.append(delay);now[0] += delay
        with patch.dict(os.environ, AMAP_WEB_SERVICE_KEY='unit-placeholder'):
            client = AmapClient(opener=lambda *a, **k: io.BytesIO(b'{"status":"1"}'),
                                min_interval_s=.5, clock=lambda: now[0], sleeper=sleep)
        client.get('/v3/direction/walking', {});client.get('/v3/direction/walking', {})
        self.assertEqual(waits, [.5])


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider, self.network = provider_for()
        self.service = WalkingRouteService(self.provider)

    def test_four_stops_three_legs_totals_and_input_unchanged(self):
        route = tiny_route();before = copy.deepcopy(route)
        walking = self.service.hydrate_dict(route)['walking']
        self.assertEqual(route, before)
        self.assertEqual(len(walking['legs']), 3)
        self.assertEqual(self.network.call_count, 3)
        self.assertEqual(walking['total_distance_m'], sum(l['distance_m'] for l in walking['legs']))
        self.assertEqual(walking['total_duration_s'], sum(l['duration_s'] for l in walking['legs']))
        self.assertEqual(walking['status'], 'AVAILABLE')
        self.assertTrue(walking['geometry']);self.assertTrue(walking['geometry_complete'])

    def test_cache_reuses_unchanged_legs_on_replan(self):
        self.service.hydrate_dict(tiny_route())
        changed = tiny_route((A, B, Location(31.179, 121.467, 'GCJ02'), D))
        result = self.service.hydrate_dict(changed)
        self.assertEqual(self.network.call_count, 5)
        self.assertTrue(result['walking_legs'][0]['cache_hit'])
        self.assertFalse(result['walking_legs'][1]['cache_hit'])

    def test_cache_is_directional_and_expiring(self):
        now = [0]
        service = WalkingRouteService(self.provider, ttl_s=10, clock=lambda: now[0])
        service.get_walking_route(A, B);service.get_walking_route(A, B)
        self.assertEqual(self.network.call_count, 1)
        service.get_walking_route(B, A);self.assertEqual(self.network.call_count, 2)
        now[0] = 10;service.get_walking_route(A, B);self.assertEqual(self.network.call_count, 3)

    def test_cache_bounds_and_defensive_copy(self):
        service = WalkingRouteService(self.provider, max_entries=1)
        first = service.hydrate_dict(tiny_route((A, B)))
        first['walking']['legs'][0]['distance_m'] = -1
        second = service.hydrate_dict(tiny_route((A, B)))
        self.assertEqual(second['walking']['legs'][0]['distance_m'], 300)
        service.get_walking_route(B, C);service.get_walking_route(A, B)
        self.assertEqual(self.network.call_count, 3)

    def test_timeout_fallback_no_fake_road_geometry(self):
        self.network.side_effect = socket.timeout()
        result = self.service.hydrate_dict(tiny_route())
        self.assertEqual(result['walking_data_status'], 'FALLBACK_ESTIMATE')
        self.assertAlmostEqual(result['walking_distance_m'], 900)
        self.assertEqual(result['walking_duration_s'], 720)
        self.assertEqual(result['route_geometry'], ())
        self.assertTrue(all(l['error_code'] == 'provider_timeout' for l in result['walking_legs']))
        # Failures are never cached as real successes.
        self.network.side_effect = lambda *a, **k: io.BytesIO(json.dumps(payload()).encode())
        self.assertEqual(self.service.hydrate_dict(tiny_route())['walking_data_status'], 'AVAILABLE')

    def test_partial_failure_cannot_draw_across_gap(self):
        self.network.side_effect = [io.BytesIO(json.dumps(payload()).encode()), socket.timeout(),
                                   io.BytesIO(json.dumps(payload()).encode())]
        result = self.service.hydrate_dict(tiny_route())
        self.assertEqual(result['walking_data_status'], 'FALLBACK_ESTIMATE')
        self.assertEqual(result['route_geometry'], ())
        self.assertEqual(len(result['walking']['geometry_segments']), 3)
        self.assertFalse(result['walking']['geometry_complete'])

    def test_unavailable_when_no_valid_estimate(self):
        route = tiny_route((A, B));route['ordered_pois'][1]['estimated_walking_minutes'] = None
        result = WalkingRouteService().hydrate_dict(route)
        self.assertEqual(result['walking_data_status'], 'UNAVAILABLE')
        self.assertIsNone(result['walking_duration_s'])

    def test_single_stop_and_explicit_approach(self):
        route = tiny_route((A,))
        result = self.service.hydrate_dict(route)
        self.assertEqual(result['walking_distance_m'], 0)
        self.assertEqual(result['walking_legs'], [])
        self.network.assert_not_called()
        route['request'].update(start_lat=B.lat, start_lng=B.lng, start_coordinate_system='GCJ-02')
        result = self.service.hydrate_dict(route)
        self.assertEqual(len(result['walking_legs']), 1)
        self.assertIsNone(result['walking_legs'][0]['from_poi_id'])

    def test_unknown_coordinate_system_falls_back_without_network(self):
        route = tiny_route((A, B));route['ordered_pois'][0]['coordinate_system'] = 'unknown'
        result = self.service.hydrate_dict(route)
        self.assertEqual(result['walking_data_status'], 'FALLBACK_ESTIMATE')
        self.network.assert_not_called()

    def test_faulty_provider_cannot_corrupt_hydration(self):
        provider = Mock();provider.get_walking_route.side_effect = RuntimeError('unexpected transport diagnostic')
        result = WalkingRouteService(provider).hydrate_dict(tiny_route())
        self.assertEqual(result['walking_data_status'], 'FALLBACK_ESTIMATE')
        self.assertNotIn('unexpected transport diagnostic', json.dumps(result))

    def test_wgs_input_uses_conversion_even_in_route_hydration(self):
        route = tiny_route((Location(31.17, 121.46, 'WGS84'), B))
        self.network.side_effect = [io.BytesIO(b'{"status":"1","locations":"121.463,31.175"}'),
                                   io.BytesIO(json.dumps(payload()).encode())]
        result = self.service.hydrate_dict(route)
        self.assertEqual(result['walking_data_status'], 'AVAILABLE')
        self.assertEqual(result['walking_legs'][0]['origin']['coordinate_system'], 'GCJ02')
        self.assertEqual(self.network.call_count, 2)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, AMAP_WEB_SERVICE_KEY='');self.env.start();self.addCleanup(self.env.stop)
        self.repo = POIRepository()
        self.provider, self.network = provider_for()
        self.service = WalkingRouteService(self.provider)

    def test_engine_calls_only_final_legs_keeps_planning_and_soft_budget(self):
        request = RouteRequest(180, preferred_zone='west_bund')
        before = RouteEngine(self.repo).generate_route(request)
        huge = payload();huge['route']['paths'][0]['duration'] = '50000'
        self.network.side_effect = lambda *a, **k: io.BytesIO(json.dumps(huge).encode())
        result = WalkingRoutePlanner(self.repo, walking_service=self.service).generate_route(request)
        self.assertEqual([s.poi_id for s in before.ordered_pois], [s.poi_id for s in result.ordered_pois])
        self.assertEqual(before.total_estimated_minutes, result.total_estimated_minutes)
        self.assertEqual(self.network.call_count, len(result.ordered_pois)-1)
        self.assertGreater(result.walking_duration_s / 60, 180)
        self.assertEqual(result.planning_duration_min, before.total_estimated_walking_minutes)
        self.assertEqual(result.walking_data_status, 'AVAILABLE')

    def test_route_entry_surprise_hydrates_only_winning_route(self):
        intent = RouteIntent(RouteMode.SURPRISE_ME, available_minutes=180, start_lat=A.lat, start_lng=A.lng,
                             preferred_zone='west_bund')
        result = RouteEntryService(self.repo, walking_service=self.service).generate(intent)
        self.assertEqual(result.status, 'success')
        self.assertEqual(self.network.call_count, len(result.route_plan.ordered_pois))
        self.assertEqual(result.route_plan.walking_data_status, 'AVAILABLE')

    def test_timeout_still_creates_valid_trip(self):
        plan, intent = load_fixture()
        self.network.side_effect = socket.timeout()
        hydrated = self.service.hydrate_walking_route(plan)
        self.assertEqual(hydrated.status, 'success')
        self.assertEqual(hydrated.walking_data_status, 'FALLBACK_ESTIMATE')
        trip = TripState.create(hydrated, intent)
        self.assertEqual(TripState.from_dict(trip.to_dict()).active_route, trip.active_route)
        self.assertNotIn('unit-placeholder', json.dumps(trip.to_dict()))

    def make_trip(self):
        plan, intent = load_fixture()
        plan = self.service.hydrate_walking_route(plan)
        store = InMemoryTripStore();core = TripService(store)
        trip = core.create_trip(plan, intent);core.start_trip(trip.trip_id)
        core.complete_stop(trip.trip_id, 'p29');core.update_elapsed_time(trip.trip_id, 60)
        return store, core, trip.trip_id

    def test_replan_versions_records_and_json_roundtrip(self):
        store, _, tid = self.make_trip();before = store.get(tid)
        result = ReplanningCoordinator(store, self.repo, walking_service=self.service).replan(
            tid, TripStateDelta(request_replan=True, remaining_minutes=60))
        self.assertTrue(result.committed, result.to_dict())
        after = store.get(tid)
        self.assertEqual(before.route_versions[0], after.route_versions[0])
        self.assertEqual(before.original_route, after.original_route)
        self.assertEqual(after.route_versions[-1]['version_id'], 'v2')
        self.assertEqual(after.active_route['walking_data_status'], 'AVAILABLE')
        self.assertEqual(len(after.replan_history), 1)
        self.assertEqual(TripState.from_dict(after.to_dict()).to_dict(), after.to_dict())

    def test_replan_failure_keeps_trip_valid(self):
        store, _, tid = self.make_trip();old = store.get(tid).route_versions[0]
        self.network.side_effect = socket.timeout()
        self.service = WalkingRouteService(self.provider)  # Force cache miss.
        result = ReplanningCoordinator(store, self.repo, walking_service=self.service).replan(
            tid, TripStateDelta(request_replan=True, remaining_minutes=60))
        self.assertTrue(result.committed, result.to_dict())
        trip = store.get(tid)
        self.assertEqual(trip.route_versions[0], old)
        self.assertEqual(trip.active_route['walking_data_status'], 'FALLBACK_ESTIMATE')
        TripState.from_dict(trip.to_dict())

    def test_no_change_replan_does_not_query_world(self):
        store, _, tid = self.make_trip()
        calls = self.network.call_count
        result = ReplanningCoordinator(store, self.repo, walking_service=self.service).replan(
            tid, TripStateDelta(request_replan=False))
        self.assertEqual(result.status, 'no_change')
        self.assertEqual(self.network.call_count, calls)

    def test_stale_save_during_hydration_preserves_concurrent_progress(self):
        store, core, tid = self.make_trip()
        coordinator = ReplanningCoordinator(store, self.repo, walking_service=WalkingRouteService(self.provider))
        def request(*a, **k):
            core.update_elapsed_time(tid, 61)
            return io.BytesIO(json.dumps(payload()).encode())
        self.network.side_effect = request
        result = coordinator.replan(tid, TripStateDelta(request_replan=True, remaining_minutes=60))
        self.assertEqual(result.status, 'stale_state_conflict')
        self.assertFalse(result.committed)
        self.assertEqual(len(store.get(tid).route_versions), 1)
        self.assertEqual(store.get(tid).elapsed_minutes, 61)

    def test_restricted_remove_hydrates_new_sequence_only(self):
        store, _, tid = self.make_trip();trip = store.get(tid);before = trip.route_versions
        mutation = RouteMutationService(self.repo, walking_service=self.service)
        stops = trip.get_remaining_stops()
        target = stops[-1]['poi_id'];stops = mutation.remove_only(stops, target)
        policy = dict(target_deadline=trip.target_total_minutes if hasattr(trip, 'target_total_minutes') else 180,
                      hard_deadline=None, time_constraint_mode='soft')
        result = mutation.build_route(trip, stops, trip.current_intent, policy)
        self.assertEqual([s['poi_id'] for s in result['ordered_pois']], [s['poi_id'] for s in stops])
        self.assertNotIn(target, [s['to_poi_id'] for s in result['walking_legs']])
        self.assertEqual(result['walking_data_status'], 'AVAILABLE')
        self.assertEqual(trip.route_versions, before)

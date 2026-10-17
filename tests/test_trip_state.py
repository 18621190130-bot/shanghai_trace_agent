"""Trip invariants against an existing successful production RoutePlan fixture."""
import copy
import json
import unittest
from unittest.mock import patch
from tools.demos.trip_demo import load_fixture
from src.trip_state import TripState, TripStateError, TripStatus, TripStateDelta, ReplanRecord

AT = '2026-10-05T10:00:00+08:00'


class TripStateTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.intent = load_fixture()
        self.ids = [s.poi_id for s in self.plan.ordered_pois]
        self.trip = TripState.create(self.plan, self.intent, clock=lambda: AT)

    def test_original_route_and_intent_reference_isolation(self):
        original = self.trip.original_route
        initial_intent = self.trip.original_intent
        self.plan.ordered_pois.clear()
        self.intent.interest_tags.append('untrusted')
        active = self.trip.active_route
        active['ordered_pois'].clear()
        current = self.trip.current_intent
        current['avoid_tags'].append('untrusted')
        self.trip.start_trip();self.trip.complete_stop(self.ids[0]);self.trip.skip_stop(self.ids[1])
        self.assertEqual(self.trip.original_route, original)
        self.assertEqual(self.trip.original_intent, initial_intent)
        self.assertEqual(self.trip.current_intent, initial_intent)
        with self.assertRaises(AttributeError):self.trip.original_route = {}

    def test_planned_start_and_repeat_preserves_progress(self):
        self.assertEqual(self.trip.status, TripStatus.PLANNED)
        self.assertIsNone(self.trip.current_poi_id)
        self.assertTrue(self.trip.start_trip());self.trip.complete_stop(self.ids[0])
        before = self.trip.to_dict()
        self.assertFalse(self.trip.start_trip())
        self.assertEqual(before, self.trip.to_dict())

    def test_complete_skip_current_and_idempotent_retries(self):
        self.trip.start_trip();self.trip.complete_stop(self.ids[0])
        self.assertEqual(self.trip.visited_poi_ids, [self.ids[0]])
        self.assertEqual(self.trip.current_poi_id, self.ids[1])
        self.trip.skip_stop(self.ids[1])
        self.assertEqual(self.trip.current_poi_id, self.ids[2])
        before = self.trip.to_dict()
        self.assertFalse(self.trip.complete_stop(self.ids[0]));self.assertFalse(self.trip.skip_stop(self.ids[1]))
        self.assertEqual(before, self.trip.to_dict())
        self.assertEqual(set(self.trip.excluded_poi_ids), {self.ids[0], self.ids[1]})

    def test_disjoint_membership_and_atomic_invalid_operations(self):
        self.trip.start_trip();self.trip.complete_stop(self.ids[0]);self.trip.skip_stop(self.ids[1])
        for method, pid in ((self.trip.skip_stop, self.ids[0]), (self.trip.complete_stop, self.ids[1]), (self.trip.complete_stop, 'unknown')):
            before = self.trip.to_dict()
            with self.assertRaises(TripStateError):method(pid)
            self.assertEqual(before, self.trip.to_dict())
        self.assertFalse(set(self.trip.remaining_poi_ids) & set(self.trip.excluded_poi_ids))

    def test_out_of_order_completion_keeps_logical_first_remaining(self):
        self.trip.start_trip();self.trip.complete_stop(self.ids[-1])
        self.assertEqual(self.trip.current_poi_id, self.ids[0])
        self.assertNotIn(self.ids[-1], self.trip.remaining_poi_ids)

    def test_invalid_states_and_terminal_resume_rejected(self):
        for operation in (lambda:self.trip.complete_stop(self.ids[0]),lambda:self.trip.skip_stop(self.ids[0]),lambda:self.trip.update_elapsed_time(1),self.trip.abandon_trip):
            with self.assertRaises(TripStateError):operation()
        self.trip.start_trip();self.trip.abandon_trip()
        with self.assertRaises(TripStateError):self.trip.start_trip()
        with self.assertRaises(TripStateError):self.trip.complete_stop(self.ids[0])
        self.assertFalse(self.trip.abandon_trip())

    def test_auto_completed_and_all_skipped_rule(self):
        self.trip.start_trip()
        for pid in self.ids:self.trip.complete_stop(pid)
        self.assertEqual(self.trip.status, TripStatus.COMPLETED)
        self.assertIsNone(self.trip.current_poi_id)
        self.assertEqual(self.trip.event_history[-1]['event_type'], 'trip_completed')
        self.assertFalse(self.trip.complete_stop(self.ids[-1]))
        with self.assertRaises(TripStateError):self.trip.start_trip()
        other = TripState.create(*load_fixture(), clock=lambda: AT);other.start_trip()
        for pid in self.ids:other.skip_stop(pid)
        self.assertEqual(other.status, TripStatus.ACTIVE)
        self.assertIsNone(other.current_poi_id)
        other.abandon_trip();self.assertEqual(other.status, TripStatus.ABANDONED)

    def test_mixed_dispositions_complete_with_real_visit(self):
        self.trip.start_trip();self.trip.complete_stop(self.ids[0])
        for pid in self.ids[1:]:self.trip.skip_stop(pid)
        self.assertEqual(self.trip.status, TripStatus.COMPLETED)
        self.assertEqual(self.trip.visited_poi_ids, [self.ids[0]])

    def test_time_budget_manual_monotonic_clamped_and_finite(self):
        self.trip.start_trip();self.trip.update_elapsed_time(30)
        self.assertEqual(self.trip.remaining_minutes, self.trip.original_minutes - 30)
        for value in (-1, True, float('inf'), float('nan'), 10**400, '30', 10):
            before = self.trip.to_dict()
            with self.assertRaises(TripStateError):self.trip.update_elapsed_time(value)
            self.assertEqual(self.trip.to_dict(), before)
        self.trip.update_elapsed_time(999);self.assertEqual(self.trip.remaining_minutes, 0)
        self.assertEqual(self.trip.status, TripStatus.ACTIVE)

    def test_version_one_history_append_only_and_role_context(self):
        version = self.trip.route_versions[0]
        self.assertEqual(version['version_id'], 'v1');self.assertEqual(version['reason'], 'initial_plan')
        self.assertEqual(version['route_snapshot'], self.trip.original_route)
        self.trip.start_trip();history = self.trip.event_history
        anchor = next(s.poi_id for s in self.plan.ordered_pois if s.effective_primary_role == 'anchor')
        self.trip.complete_stop(anchor)
        self.assertEqual(self.trip.event_history[:len(history)], history)
        self.assertTrue(self.trip.get_journey_context()['has_visited_anchor'])
        self.assertEqual(self.trip.get_journey_context()['has_visited_anchor_or_supporting_count'], 1)
        history.clear();self.assertGreater(len(self.trip.event_history), 0)
        self.assertEqual(self.trip.replan_history, [])

    def test_json_roundtrip_at_all_states_and_tamper_rejected(self):
        self.trip.start_trip();self.trip.update_elapsed_time(15);self.trip.complete_stop(self.ids[0]);self.trip.skip_stop(self.ids[1])
        raw = self.trip.to_dict()
        self.assertEqual(TripState.from_dict(json.loads(json.dumps(raw))).to_dict(), raw)
        for key, value in (('remaining_poi_ids', self.ids), ('status', 'COMPLETED'), ('elapsed_minutes', -1), ('current_intent', {}), ('replan_history', [{}])):
            bad = copy.deepcopy(raw);bad[key] = value
            with self.assertRaises(TripStateError):TripState.from_dict(bad)
        for bad in (None, [], {}):
            with self.assertRaises(TripStateError):TripState.from_dict(bad)

    def test_completed_and_abandoned_roundtrip(self):
        self.trip.start_trip()
        for pid in self.ids:self.trip.complete_stop(pid)
        self.assertEqual(TripState.from_dict(self.trip.to_dict()).to_dict(), self.trip.to_dict())
        other = TripState.create(*load_fixture(), clock=lambda: AT);other.start_trip();other.abandon_trip()
        self.assertEqual(TripState.from_dict(other.to_dict()).to_dict(), other.to_dict())

    def test_empty_failed_duplicate_and_budget_mismatch_refused(self):
        for change in ('empty', 'failed', 'duplicate', 'budget'):
            plan, intent = load_fixture()
            if change == 'empty':plan.ordered_pois.clear()
            elif change == 'failed':plan.status = 'composition_failure'
            elif change == 'duplicate':plan.ordered_pois.append(plan.ordered_pois[0])
            else:intent.available_minutes += 1
            with self.assertRaises(TripStateError):TripState.create(plan, intent)

    def test_does_not_rejudge_short_places_plan_or_call_engine(self):
        plan, intent = load_fixture();plan.ordered_pois = plan.ordered_pois[:1]
        with patch('src.route_engine.RouteEngine.generate_route', side_effect=AssertionError('No planning')):
            trip = TripState.create(plan, intent, clock=lambda: AT)
            trip.start_trip();trip.complete_stop(plan.ordered_pois[0].poi_id)
            self.assertEqual(trip.status, TripStatus.COMPLETED)

    def test_timestamp_validation_and_deterministic_events(self):
        with self.assertRaises(TripStateError):self.trip.start_trip(timestamp='2026-10-05')
        self.trip.start_trip()
        with self.assertRaises(TripStateError):self.trip.complete_stop(self.ids[0], timestamp='2026-10-04T00:00:00+00:00')
        other = TripState.create(*load_fixture(), trip_id=self.trip.trip_id, clock=lambda: AT)
        other.start_trip();self.assertEqual(self.trip.to_dict(), other.to_dict())

    def test_future_current_snapshot_fixture_cannot_alias_originals(self):
        original = self.trip.original_route;intent = self.trip.original_intent
        # Internal future-integration fixtures only; no public replan/delta API.
        self.trip._data['active_route']['explanation'] = 'future active version fixture'
        self.trip._data['current_intent']['avoid_tags'].append('museum_visit')
        self.assertEqual(self.trip.original_route, original)
        self.assertEqual(self.trip.original_intent, intent)
        self.assertEqual(self.trip.route_versions[0]['route_snapshot'], original)
        with self.assertRaises(TripStateError):TripState.from_dict(self.trip.to_dict())

    def test_journey_context_keeps_visited_anchor_when_remaining_has_none(self):
        plan, intent = load_fixture();plan.ordered_pois = plan.ordered_pois[:4]
        for stop, role in zip(plan.ordered_pois, ('anchor', 'supporting_stop', 'supporting_stop', 'transition_stop')):
            stop.effective_primary_role = role
        trip = TripState.create(plan, intent, clock=lambda: AT);trip.start_trip()
        trip.complete_stop(plan.ordered_pois[0].poi_id);trip.complete_stop(plan.ordered_pois[1].poi_id)
        context = trip.get_journey_context()
        self.assertTrue(context['has_visited_anchor'])
        self.assertEqual(context['remaining_roles'], ['supporting_stop', 'transition_stop'])
        self.assertEqual(context['has_visited_anchor_or_supporting_count'], 2)

    def test_event_rewrite_unknown_event_and_reserved_replanning_rejected(self):
        self.trip.start_trip();self.trip.complete_stop(self.ids[0]);raw = self.trip.to_dict()
        for change in ('event_id', 'payload', 'event_type', 'replanning'):
            bad = copy.deepcopy(raw)
            if change == 'event_id':bad['event_history'][0]['event_id'] = 'forged'
            elif change == 'payload':bad['event_history'][1]['payload']['poi_id'] = self.ids[1]
            elif change == 'event_type':bad['event_history'][0]['event_type'] = 'replan_started'
            else:bad['status'] = 'REPLANNING'
            with self.assertRaises(TripStateError):TripState.from_dict(bad)

    def test_must_go_obligation_and_explicit_skip_audit(self):
        plan, intent = load_fixture();intent.must_go_poi_ids = [self.ids[0]]
        trip = TripState.create(plan, intent, clock=lambda: AT);trip.start_trip()
        self.assertIn(self.ids[0], trip.must_go_remaining)
        trip.skip_stop(self.ids[0]);self.assertNotIn(self.ids[0], trip.must_go_remaining)
        self.assertEqual(trip.get_journey_context()['skipped_must_go_ids'], [self.ids[0]])

    def test_delta_validation_schema_and_conflicts(self):
        self.assertFalse(TripStateDelta.schema()['additionalProperties'])
        delta = TripStateDelta.from_dict(dict(remaining_minutes=25, pace='quick', skip_poi_ids=[self.ids[0]], request_replan=True))
        self.assertEqual(TripStateDelta.from_dict(delta.to_dict()).to_dict(), delta.to_dict())
        for raw in ({'remaining_minutes': True}, {'remaining_minutes': -1}, {'pace': 'fast'}, {'request_replan': 1}, {'skip_poi_ids': [self.ids[0]]*2}, {'new_field': 1}, {'add_interest_tags': ['history'], 'remove_interest_tags': ['history']}):
            with self.assertRaises(TripStateError):TripStateDelta.from_dict(raw)
        with self.assertRaises(TripStateError):TripStateDelta.from_dict({'skip_poi_ids': ['unknown']}, allowed_poi_ids=self.ids)
        with self.assertRaises(TripStateError):TripStateDelta.from_dict({'add_interest_tags': ['unknown']}, taxonomy={'interest_tags': {'history': 'History'}})
        record = ReplanRecord('time_reduced', 'v1', 'v2', {}, {}, AT)
        self.assertEqual(record.to_dict()['old_route_version'], 'v1')

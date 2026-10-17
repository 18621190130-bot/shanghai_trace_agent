import unittest
from tools.demos.trip_demo import load_fixture
from src.trip_state import TripState, TripStateError
from src.trip_store import InMemoryTripStore, TripService

AT = '2026-10-05T10:00:00+08:00'


class TripStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryTripStore(clock=lambda: AT)
        self.service = TripService(self.store, clock=lambda: AT)
        self.plan, self.intent = load_fixture()
        self.trip = self.service.create_trip(self.plan, self.intent)
        self.pid = self.plan.ordered_pois[0].poi_id

    def test_independent_ids_progress_and_store_copies(self):
        other = self.service.create_trip(self.plan, self.intent)
        self.assertNotEqual(self.trip.trip_id, other.trip_id)
        self.service.start_trip(self.trip.trip_id);self.service.complete_stop(self.trip.trip_id, self.pid)
        self.assertEqual(self.service.get_trip(other.trip_id).visited_poi_ids, [])
        local = self.store.get(other.trip_id);local.start_trip()
        self.assertEqual(self.store.get(other.trip_id).status, 'PLANNED')

    def test_duplicate_missing_and_delete(self):
        with self.assertRaises(TripStateError):self.store.create(self.trip)
        with self.assertRaises(KeyError):self.store.get('missing')
        with self.assertRaises(KeyError):self.store.save(TripState.create(self.plan, self.intent, clock=lambda: AT))
        self.store.delete(self.trip.trip_id)
        with self.assertRaises(KeyError):self.store.get(self.trip.trip_id)

    def test_append_only_save_rejects_stale_conflicting_branch(self):
        self.service.start_trip(self.trip.trip_id)
        first = self.store.get(self.trip.trip_id);second = self.store.get(self.trip.trip_id)
        first.complete_stop(self.pid);self.store.save(first)
        second.skip_stop(self.pid)
        with self.assertRaises(TripStateError):self.store.save(second)
        with self.assertRaises(TripStateError):self.store.save(self.trip)
        self.assertEqual(self.store.get(self.trip.trip_id).visited_poi_ids, [self.pid])

    def test_service_views_serialization_time_and_failed_operation(self):
        tid = self.trip.trip_id;self.service.start_trip(tid);self.service.update_elapsed_time(tid, 20)
        before = self.service.serialize_trip(tid)
        with self.assertRaises(TripStateError):self.service.complete_stop(tid, 'unknown')
        self.assertEqual(before, self.service.serialize_trip(tid))
        self.assertEqual(self.service.get_original_route(tid), self.service.get_active_route(tid))
        self.assertEqual(len(self.service.get_remaining_stops(tid)), len(self.plan.ordered_pois))
        self.assertFalse(self.service.get_journey_context(tid)['has_visited_anchor'])
        self.assertEqual(self.service.get_trip(tid).remaining_minutes, 160)

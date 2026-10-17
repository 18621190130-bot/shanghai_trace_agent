"""Persistence boundary: copy-isolated snapshots with append-only save checks."""
from typing import Protocol
from threading import RLock
from .trip_state import TripState, TripStateError, utc_now


class TripStore(Protocol):
    def create(self, trip: TripState) -> None: ...
    def get(self, trip_id: str) -> TripState: ...
    def save(self, trip: TripState) -> None: ...
    def save_if_revision(self, trip: TripState, expected_revision: int) -> None: ...
    def delete(self, trip_id: str) -> None: ...


class StaleStateConflict(TripStateError):
    """A newer stored state must never be overwritten."""


class InMemoryTripStore:
    def __init__(self, *, clock=utc_now):
        self._snapshots = {}
        self._clock = clock
        self._lock = RLock()

    def create(self, trip):
        raw = TripState.from_dict(trip.to_dict(), clock=self._clock).to_dict()
        if trip.trip_id in self._snapshots:
            raise TripStateError('Trip ID already exists')
        self._snapshots[trip.trip_id] = raw

    def get(self, trip_id):
        if trip_id not in self._snapshots:
            raise KeyError('Trip not found: ' + str(trip_id))
        trip = TripState.from_dict(self._snapshots[trip_id], clock=self._clock)
        trip._loaded_revision = trip.state_revision
        return trip

    def save(self, trip):
        return self.save_if_revision(trip, getattr(trip, '_loaded_revision', trip.state_revision))

    def save_if_revision(self, trip, expected_revision):
        with self._lock:
            return self._save_if_revision(trip, expected_revision)

    def _save_if_revision(self, trip, expected_revision):
        raw = TripState.from_dict(trip.to_dict(), clock=self._clock).to_dict()
        if trip.trip_id not in self._snapshots:
            raise KeyError('Trip not found: ' + trip.trip_id)
        old = self._snapshots[trip.trip_id]
        if type(expected_revision) is not int or expected_revision != old['state_revision']:
            raise StaleStateConflict('stale_state_conflict')
        for key in ('original_route', 'original_intent', 'created_at'):
            if raw[key] != old[key]:
                raise TripStateError('Immutable trip snapshot changed: ' + key)
        if raw['route_versions'][:len(old['route_versions'])] != old['route_versions']:
            raise TripStateError('Route version history rewrite')
        events = old['event_history']
        if raw['event_history'][:len(events)] != events:
            raise TripStateError('Stale/conflicting save or event history rewrite')
        self._snapshots[trip.trip_id] = raw
        trip._loaded_revision = trip.state_revision

    def delete(self, trip_id):
        if trip_id not in self._snapshots:
            raise KeyError('Trip not found: ' + str(trip_id))
        del self._snapshots[trip_id]


class TripService:
    """Same core operations for future button and delta adapters."""
    def __init__(self, store: TripStore, *, clock=utc_now):
        self.store = store
        self.clock = clock

    def create_trip(self, route_plan, route_intent, **options):
        trip = TripState.create(route_plan, route_intent, clock=self.clock, **options)
        self.store.create(trip)
        return self.store.get(trip.trip_id)

    def get_trip(self, trip_id):
        return self.store.get(trip_id)

    def _operation(self, trip_id, operation, *args, **kwargs):
        trip = self.store.get(trip_id)
        expected = kwargs.pop('expected_revision', None)
        if expected is not None and trip.state_revision != expected:raise StaleStateConflict('stale_state_conflict')
        getattr(trip, operation)(*args, **kwargs)
        if expected is None:self.store.save(trip)
        else:self.store.save_if_revision(trip, expected)
        return self.store.get(trip_id)

    def start_trip(self, trip_id, **kwargs):
        return self._operation(trip_id, 'start_trip', **kwargs)

    def complete_stop(self, trip_id, poi_id, **kwargs):
        return self._operation(trip_id, 'complete_stop', poi_id, **kwargs)

    def skip_stop(self, trip_id, poi_id, **kwargs):
        return self._operation(trip_id, 'skip_stop', poi_id, **kwargs)

    def update_elapsed_time(self, trip_id, minutes, **kwargs):
        return self._operation(trip_id, 'update_elapsed_time', minutes, **kwargs)

    def abandon_trip(self, trip_id, **kwargs):
        return self._operation(trip_id, 'abandon_trip', **kwargs)

    def cancel_planned_trip(self, trip_id, **kwargs):
        return self._operation(trip_id, 'cancel_planned_trip', **kwargs)

    def get_original_route(self, trip_id):
        return self.get_trip(trip_id).get_original_route()

    def get_active_route(self, trip_id):
        return self.get_trip(trip_id).get_active_route()

    def get_current_route(self, trip_id):
        return self.get_active_route(trip_id)

    def get_route_history(self, trip_id):
        trip = self.get_trip(trip_id)
        records = {r['new_route_version_id']: r for r in trip.replan_history}
        return [dict(version, replan_record=records.get(version['version_id'])) for version in trip.route_versions]

    def get_latest_replan_summary(self, trip_id):
        history = self.get_trip(trip_id).replan_history
        return history[-1] if history else None

    def apply_core_action(self, trip_id, action, *, poi_id=None, elapsed_minutes=None, expected_revision):
        """Execute a target interpreted against exactly the loaded revision."""
        trip = self.store.get(trip_id)
        if trip.state_revision != expected_revision:
            raise StaleStateConflict('stale_state_conflict')
        if action == 'complete_stop':changed = trip.complete_stop(poi_id)
        elif action == 'skip_stop':changed = trip.skip_stop(poi_id)
        elif action == 'update_elapsed_time':changed = trip.update_elapsed_time(elapsed_minutes)
        else:raise TripStateError('Unsupported Core action')
        self.store.save_if_revision(trip, expected_revision)
        return dict(action=action, poi_id=poi_id, changed=changed, state_revision=trip.state_revision,
                    status=trip.status, saved=True)

    def get_remaining_stops(self, trip_id):
        return self.get_trip(trip_id).get_remaining_stops()

    def get_journey_context(self, trip_id):
        return self.get_trip(trip_id).get_journey_context()

    def serialize_trip(self, trip_id):
        return self.get_trip(trip_id).to_dict()

"""Offline Trip State acceptance demo using a previously successful route."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from pathlib import Path
from src.intent_models import RouteIntent
from src.models import RoutePlan, RouteStop
from src.trip_state import TripState

DEFAULT_FIXTURE = PROJECT_ROOT / 'data/poi_pipeline/promotion/production_cli_4.txt'


def load_fixture(path=DEFAULT_FIXTURE):
    """Accept existing EntryResult JSON; does not generate any route."""
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    route = value['route_plan']
    stops = [RouteStop(**{k: v for k, v in s.items() if k not in
                         ('estimated_distance_from_previous', 'estimated_walking_minutes_from_previous')})
             for s in route['ordered_pois']]
    return RoutePlan(**{**route, 'ordered_pois': stops}), RouteIntent.from_dict(value['intent'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route-fixture', type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args(argv)
    plan, intent = load_fixture(args.route_fixture)
    trip = TripState.create(plan, intent)
    ids = [s.poi_id for s in plan.ordered_pois]
    print('Create Trip / Status:', trip.status)
    trip.start_trip()
    print('Start / Status:', trip.status, '/ Current:', trip.current_poi_id)
    trip.complete_stop(ids[0])
    print('Complete / Visited:', trip.visited_poi_ids, '/ Current:', trip.current_poi_id)
    if len(ids) > 1:
        trip.skip_stop(ids[1])
        print('Skip / Skipped:', trip.skipped_poi_ids, '/ Current:', trip.current_poi_id)
    print('Original:', [s['poi_id'] for s in trip.get_original_route()['ordered_pois']])
    print('Active sequence:', [s['poi_id'] for s in trip.get_active_route()['ordered_pois']])
    print('Active remaining:', trip.remaining_poi_ids)
    print('Events:', [e['event_type'] for e in trip.event_history])
    print('Journey context:', json.dumps(trip.get_journey_context(), ensure_ascii=False))
    restored = TripState.from_dict(json.loads(json.dumps(trip.to_dict())))
    print('JSON roundtrip:', restored.to_dict() == trip.to_dict())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Offline deterministic replanning against the frozen production 59 POIs."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from tools.demos.trip_demo import load_fixture
from src.trip_replanning import ReplanningCoordinator, ReplanReason
from src.trip_state import TripState, TripStateDelta
from src.trip_store import InMemoryTripStore, TripService

SCENARIOS = ('time_reduced', 'skip_and_replan', 'avoid_museums', 'add_must_go')
AT = '2026-10-05T10:00:00+08:00'


def run_scenario(name):
    if name not in SCENARIOS:
        raise ValueError('Unknown scenario')
    plan, intent = load_fixture()
    store = InMemoryTripStore(clock=lambda: AT)
    service = TripService(store, clock=lambda: AT)
    trip = service.create_trip(plan, intent, trip_id='demo-' + name)
    tid = trip.trip_id
    service.start_trip(tid)
    service.complete_stop(tid, 'p29')
    service.update_elapsed_time(tid, 60)
    if name == 'time_reduced':
        delta = TripStateDelta(remaining_minutes=60, request_replan=True)
        reason = ReplanReason.TIME_REDUCED
    elif name == 'skip_and_replan':
        service.skip_stop(tid, 'p30')
        delta = TripStateDelta(request_replan=True)
        reason = ReplanReason.STOP_SKIPPED
    elif name == 'avoid_museums':
        delta = TripStateDelta(add_avoid_tags=['museum_visit'], request_replan=True)
        reason = ReplanReason.AVOIDANCE_CHANGED
    else:
        delta = TripStateDelta(add_must_go_poi_ids=['p36'], request_replan=True)
        reason = ReplanReason.MUST_GO_ADDED
    before = store.get(tid).to_dict()
    result = ReplanningCoordinator(store).replan(tid, delta, primary_reason=reason)
    after = store.get(tid).to_dict()
    roundtrip = TripState.from_dict(json.loads(json.dumps(after))).to_dict() == after
    return dict(scenario=name, state_before=before, result=result.to_dict(), state_after=after,
                serialization_roundtrip=roundtrip)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=SCENARIOS, default='time_reduced')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    evidence = run_scenario(args.scenario)
    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        before, result, after = (evidence[k] for k in ('state_before', 'result', 'state_after'))
        def route(value):return ' → '.join(s['poi_id'] for s in value['ordered_pois'])
        print('Scenario:', args.scenario, '/ Trip:', after['status'])
        print('Original Route:', route(before['original_route']))
        print('Visited:', before['visited_poi_ids'], '/ Skipped:', before['skipped_poi_ids'])
        print('Current Version:', before['route_versions'][-1]['version_id'])
        print('Replan Reason:', result['reason'])
        print('Effective Remaining Time:', result['effective_remaining_minutes'], 'min')
        print('Proposed Route:', route(result['proposed_route']) if result['proposed_route'] else '(none)')
        policy = result['diagnostics'].get('in_trip_policy', {})
        print('Journey Context:', before['visited_poi_ids'], '/ visited roles:',
              result['diagnostics'].get('remaining_request', {}).get('journey_context', {}).get('visited_roles'))
        print('In-trip minimum:', 'PASS' if policy.get('minimum_passed') else 'FAIL')
        print('In-trip composition:', 'PASS' if policy.get('composition_passed') else 'FAIL')
        print('Commit:', result['status'], '/ committed:', result['committed'])
        print('Current Version:', after['route_versions'][-1]['version_id'])
        print('Original Route:', route(after['original_route']))
        print('Active Route:', route(after['active_route']))
        print('JSON roundtrip:', evidence['serialization_roundtrip'])
        print('DEFERRED TO PHASE 3B MAP ROUTING; logical origin is not GPS.')
    return 0 if evidence['result']['committed'] and evidence['serialization_roundtrip'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

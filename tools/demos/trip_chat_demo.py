"""In-trip command demo: exact offline mock fixtures by default; --live opts into DeepSeek."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from tools.demos.trip_demo import load_fixture
from src.llm_client import DeepSeekLLMClient, MockLLMClient
from src.poi_repository import POIRepository
from src.trip_action_fixtures import ACTION_FIXTURES as TRIP_COMMAND_FIXTURES
from src.trip_conversation import ConversationalTripService
from src.trip_store import InMemoryTripStore, TripService
from src.trip_action_rendering import render_mutation, render_nlu_trace, public_result, render_read_result


def build_demo(*, live=False):
    plan, intent = load_fixture()
    store = InMemoryTripStore()
    core = TripService(store)
    trip = core.create_trip(plan, intent)
    core.start_trip(trip.trip_id)
    # A cached route with explicitly saved progress is the entire starting point.
    core.complete_stop(trip.trip_id, plan.ordered_pois[0].poi_id)
    core.update_elapsed_time(trip.trip_id, 60)
    client = DeepSeekLLMClient(max_tokens=2400) if live else MockLLMClient(fixtures=TRIP_COMMAND_FIXTURES)
    return ConversationalTripService(store, POIRepository(), client, trip_service=core), trip.trip_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true', help='Explicit live DeepSeek API; requires process DEEPSEEK_API_KEY and may incur cost.')
    mode.add_argument('--mock', action='store_true', help='Default: exact documented fixtures only; never falls back to a live API.')
    parser.add_argument('--text', help='One in-trip utterance; omit for a cached-trip interactive session.')
    parser.add_argument('--json', action='store_true', help='Structured result; one-shot only, requires --text.')
    parser.add_argument('--list-fixtures', action='store_true', help='List supported mock utterances without calling a provider.')
    parser.add_argument('--trace-nlu', action='store_true', help='Sanitized semantic action/execution trace.')
    args = parser.parse_args(argv)
    if args.list_fixtures:
        print(json.dumps(list(TRIP_COMMAND_FIXTURES), ensure_ascii=False, indent=2));return 0
    if args.json and not args.text:parser.error('--json requires --text')
    service, tid = build_demo(live=args.live)
    metadata = {'mode': 'live DeepSeek' if args.live else 'mock exact fixtures',
                'initial_route_source': 'cached production fixture', 'production_poi_count': 59,
                'saved_initial_progress': 'first stop visited; elapsed 60 minutes',
                'location_basis': 'logical stop, not GPS; DEFERRED TO PHASE 3B MAP ROUTING'}
    if not args.json:
        print('Mode:', metadata['mode'])
        print('Initial route source:', metadata['initial_route_source'])
        print('Saved progress:', metadata['saved_initial_progress'])
        if not args.live:print('Use --list-fixtures for offline examples, or --live for other wording. No network fallback.')
    def turn(text):
        result = service.handle_turn(tid, text).to_dict()
        if args.json:print(json.dumps(dict(metadata=metadata, result=public_result(result, trace_nlu=args.trace_nlu)), ensure_ascii=False, indent=2))
        else:
            print('Assistant:', result['status'], '/', result['user_facing_summary'].get('headline', ''))
            for reason in result['user_facing_summary'].get('reasons', []):print(' ', reason)
            if result['clarification']:
                for i, choice in enumerate(result['clarification']['options'], 1):print(f"  {i}. {choice['label']}")
            if result.get('mutation_result'):render_mutation(result['mutation_result'])
            if result['read_result']:render_read_result(result['read_result'])
            if result['error_code']:print('Structured error:', result['error_code'])
            if args.trace_nlu and result.get('nlu_trace'):render_nlu_trace(result['nlu_trace'])
        return result
    if args.text:
        result = turn(args.text)
        return 1 if result['status'] in ('provider_error', 'parse_error', 'invalid_command', 'stale_state_conflict') else 0
    print('Cached-trip in-trip session only. Type quit to exit; cancel clears pending clarification.')
    while True:
        try:text = input('You: ')
        except (EOFError, KeyboardInterrupt):break
        if text.strip().casefold() in ('quit', 'exit'):break
        turn(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

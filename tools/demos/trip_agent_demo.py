"""Continuous trip agent: offline mock by default; explicit --live uses DeepSeek."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from src.llm_client import DeepSeekLLMClient, MockLLMClient
from src.poi_repository import POIRepository
from src.trip_agent import TripAgentService
from src.trip_agent_fixtures import AGENT_FIXTURES, FULL_JOURNEY_INITIAL
from src.trip_action_rendering import render_mutation, render_nlu_trace, public_result, render_read_result


def build_agent(*, live=False, client=None):
    return TripAgentService(POIRepository(), client or (DeepSeekLLMClient(max_tokens=2400) if live else MockLLMClient(fixtures=AGENT_FIXTURES)))


def full_journey():
    agent = build_agent()
    session = agent.create_session(session_id='full-journey')
    turns = []
    def turn(text):
        result = agent.handle_turn(session.session_id, text).to_dict()
        turns.append(dict(user_text=text, result=result))
        return result
    for text in (FULL_JOURNEY_INITIAL, 'start', "I've finished this stop.", 'Skip this place.',
                 'I only have one hour left.', 'Why did you change my route?',
                 'What changes have been made to my route?', 'Show me my original route.'):
        result = turn(text)
        if result['status'] in ('provider_error', 'parse_error', 'invalid_state', 'replan_failed'):
            raise RuntimeError('Full journey failed: ' + result['status'])
    for _ in range(60):
        trip = agent.trip_store.get(result['trip_id'])
        if trip.status == 'COMPLETED':break
        result = turn("I've finished this stop.")
    else:raise RuntimeError('Completion did not terminate')
    turn('summary')
    return dict(provider='mock', initial_route_source='RouteEntryService + RouteEngine',
                session_id=session.session_id, trip_id=result['trip_id'], turns=turns,
                final_session=agent.sessions.get(session.session_id).to_dict(),
                final_trip=agent.trip_store.get(result['trip_id']).to_dict())


class AgentResponseRenderer:
    """Grounded rendering only; no answer model or new routing decisions."""
    def __init__(self, *, trace_nlu=False):self.trace_nlu = trace_nlu

    def render(self, result):
        print('Assistant:', result['user_facing_summary'].get('headline', result['status']))
        print('Phase:', result['session_phase'])
        for reason in result['user_facing_summary'].get('reasons', []):print(' ', reason)
        completed = result['user_facing_summary'].get('completed_stop')
        if completed:print('Completed:', completed['name'])
        if result['route']:
            print('Route:', ' → '.join(p.get('name_en', p.get('name', '')) for p in result['route']['ordered_pois']))
        if result['clarification']:
            c = result['clarification']
            if c.get('question'):print(c['question'])
            for q in c.get('questions', []):print(q['question'])
            for i, option in enumerate(c.get('options', []), 1):print(f"  {i}. {option['label']}")
        if result['progress']:
            p = result['progress'];current = p['current_stop']
            print('Current planned stop:', current['name'] if current else 'none', '| remaining:', p['remaining_count'],
                  '| minutes:', p['remaining_minutes'], '| version:', p['current_route_version'])
        if result['route_change']:
            c = result['route_change'];print('Route updated:', c['old_version'], '→', c['new_version'])
            for key in ('removed_stops', 'added_stops', 'kept_stops'):
                print(key.replace('_', ' '), ':', ', '.join(p['name'] for p in c[key]))
        if result.get('mutation_result'):render_mutation(result['mutation_result'])
        if result['read_result']:
            query = result['read_result']['query_type'];value = result['read_result']['value']
            if query == 'show_route_history':
                for version in value:
                    route = version['route_snapshot']
                    budget = version['effective_remaining_minutes']
                    if budget is None:budget = route['request']['available_minutes']
                    print(version['version_id'], '|', version['reason'].replace('_', ' '), '| remaining budget:', budget)
                    print('  ', ' → '.join(p['name_en'] for p in route['ordered_pois']))
            elif query == 'why_latest_replan':
                for key in ('removed_stops', 'added_stops', 'kept_stops'):
                    print(key.replace('_', ' '), ':', ', '.join(p['name'] for p in value.get(key, [])))
            elif query in ('multiple_read_queries', 'show_progress'):render_read_result(result['read_result'])
        if result['trip_summary']:
            s = result['trip_summary']
            print('Trip:', s['status'], '| visited:', ', '.join(p['name'] for p in s['visited']),
                  '| skipped:', ', '.join(p['name'] for p in s['skipped']), '| replans:', s['replan_count'])
            print('Original route:', ' → '.join(p['name_en'] for p in s['original_route']['ordered_pois']))
            print('Final route:', ' → '.join(p['name_en'] for p in s['current_route']['ordered_pois']))
            print('Minutes: original', s['original_minutes'], '| elapsed', s['elapsed_minutes'], '| remaining', s['remaining_minutes'])
        if result['error_code']:
            print('Error:', result['error_code'])
            if result['status'] == 'provider_error':print('For offline wording use --list-fixtures; --live requires a configured provider. There is no live fallback.')
        if self.trace_nlu and result.get('nlu_trace'):render_nlu_trace(result['nlu_trace'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--live', action='store_true', help='Explicit DeepSeek calls; process DEEPSEEK_API_KEY required; may incur cost.')
    modes.add_argument('--mock', action='store_true', help='Default exact offline fixtures, no live fallback.')
    parser.add_argument('--list-fixtures', action='store_true')
    parser.add_argument('--json', action='store_true', help='Structured scenario output or interactive JSON per turn.')
    parser.add_argument('--auto-start', action='store_true', help='Explicit opt-in to start after an accepted initial route.')
    parser.add_argument('--trace-nlu', action='store_true', help='Explicit sanitized action interpretation/execution trace; no prompts or credentials.')
    parser.add_argument('--scenario', choices=['full_journey'])
    args = parser.parse_args(argv)
    if args.list_fixtures:print(json.dumps(list(AGENT_FIXTURES), ensure_ascii=False, indent=2));return 0
    renderer = AgentResponseRenderer(trace_nlu=args.trace_nlu)
    if args.scenario:
        if args.live:parser.error('The reproducible scenario is mock only; use interactive --live for human acceptance.')
        trace = full_journey()
        if args.json:
            for turn in trace['turns']:turn['result'] = public_result(turn['result'], trace_nlu=args.trace_nlu)
            print(json.dumps(trace, ensure_ascii=False, indent=2))
        else:
            print('Provider: MOCK | Initial route: RouteEntryService + RouteEngine')
            for turn in trace['turns']:print('You:', turn['user_text']);renderer.render(turn['result'])
        return 0
    agent = build_agent(live=args.live);session = agent.create_session()
    if not args.json:
        print('Provider:', 'LIVE DeepSeek (may incur cost)' if args.live else 'MOCK (exact fixtures; no network fallback)')
        print('Describe your initial walk. Type quit to exit. A route remains PLANNED until start.')
    while True:
        try:text = input('' if args.json else 'You: ')
        except (EOFError, KeyboardInterrupt):break
        if text.strip().casefold() in ('quit', 'exit'):break
        result = agent.handle_turn(session.session_id, text).to_dict()
        if args.json:print(json.dumps(public_result(result, trace_nlu=args.trace_nlu), ensure_ascii=False))
        else:renderer.render(result)
        if args.auto_start and result['status'] == 'route_ready':
            result = agent.handle_turn(session.session_id, 'start').to_dict()
            if args.json:print(json.dumps(public_result(result, trace_nlu=args.trace_nlu), ensure_ascii=False))
            else:renderer.render(result)
    return 0


if __name__ == '__main__':raise SystemExit(main())

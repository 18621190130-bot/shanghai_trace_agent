"""Human-run action interpretation evaluation; never executes a trip or planner."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from types import SimpleNamespace

from src.llm_client import DeepSeekLLMClient, LLMClientError, MockLLMClient
from src.poi_repository import POIRepository
from src.trip_actions import ActionParseError, ActionPOIResolver, TripActionParser
from src.trip_action_fixtures import ACTION_FIXTURES, ACCEPTANCE_CASES


CONTEXT = dict(trip_status='ACTIVE', current_logical_stop={'en': 'West Bund Museum', 'zh': '西岸美术馆'},
               visible_remaining_route=[{'en': n} for n in ('West Bund Museum', 'West Bund Art Center', 'Long Museum (West Bund)')],
               visited_stop_names=[{'en': 'TANK Shanghai'}], skipped_stop_names=[],
               current_interests=['architecture'], current_avoid_preferences=['museum_visit'],
               must_go_remaining_names=[], remaining_minutes=180, current_pace='standard', time_constraint_mode='soft')


def signature(proposal, resolver):
    # A read-only name/reference view, NOT a TripState or executable journey.
    current = resolver.resolve(CONTEXT['current_logical_stop']['en'])['poi_id']
    future = [resolver.resolve(p['en'])['poi_id'] for p in CONTEXT['visible_remaining_route']]
    visited = [resolver.resolve(p['en'])['poi_id'] for p in CONTEXT['visited_stop_names']]
    view = SimpleNamespace(current_poi_id=current, remaining_poi_ids=future, visited_poi_ids=visited,
                           original_route={'ordered_pois': [{'poi_id': pid} for pid in visited+future]})
    def name(value):
        result = resolver.resolve(value, view)
        return result.get('poi_id', value.casefold())
    rows = []
    for action in proposal['actions']:
        rows.append((action['action_type'], tuple(sorted(name(t) for t in action['target_mentions'])),
                     tuple(sorted(name(t) for t in action['secondary_target_mentions'])), tuple(sorted(action['preference_tags'])),
                     action['time_value_minutes'], action['time_constraint_mode'], action['pace'], action['position_relation'], action['explicit_replan'], action['request_matching_insert']))
    return sorted(rows, key=repr), proposal['needs_clarification']


def evaluate(client, cases=None):
    repository = POIRepository();parser = TripActionParser(repository, client);resolver = ActionPOIResolver(repository)
    cases = ACCEPTANCE_CASES if cases is None else cases;results = []
    provider_failed = False
    for case in cases:
        row = dict(text=case['text'], category=case['category'], expected=case['expected'], actual=None)
        if provider_failed:row.update(status='NOT_RUN', error='Stopped after provider failure');results.append(row);continue
        try:
            actual = parser.parse(case['text'], CONTEXT).to_dict();row['actual'] = actual
            row['status'] = 'PASS' if signature(actual, resolver) == signature(case['expected'], resolver) else 'FAIL'
        except LLMClientError as exc:
            row.update(status='FAIL', error=exc.kind);provider_failed = True
        except ActionParseError as exc:row.update(status='FAIL', error=exc.status)
        from src.trip_action_rendering import safe_trace
        row['trace'] = safe_trace(parser.last_trace);results.append(row)
    core = [r for r in results if r['category'] in ('REMOVE', 'ADD', 'MUST_GO', 'READ', 'TIME')]
    complex_cases = [r for r in results if r['category'] in ('COMPOUND', 'REVERSAL', 'REORDER')]
    def rate(rows):return sum(r['status'] == 'PASS' for r in rows)/len(rows) if rows else 0
    complete = len(results) == len(ACCEPTANCE_CASES) and {r['text'] for r in results} == {r['text'] for r in ACCEPTANCE_CASES} and all(r['status'] != 'NOT_RUN' for r in results)
    return dict(cases=results, case_count=len(results), passed=sum(r['status'] == 'PASS' for r in results),
                core_pass_rate=rate(core), complex_pass_rate=rate(complex_cases),
                acceptance_complete=complete,
                thresholds_passed=bool(complete and core and complex_cases and rate(core) == 1 and rate(complex_cases) >= .95),
                evaluation_scope='NLU only; no TripState mutations or RouteEngine calls')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--live', action='store_true', help='Explicit human-run DeepSeek evaluation; may incur API cost.')
    modes.add_argument('--mock', action='store_true', help='Offline fixture/schema harness check, not measured language-model accuracy.')
    parser.add_argument('--json', action='store_true');parser.add_argument('--limit', type=int, default=len(ACCEPTANCE_CASES))
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > len(ACCEPTANCE_CASES):parser.error('limit must be within the acceptance set')
    client = DeepSeekLLMClient(max_tokens=2400) if args.live else MockLLMClient(fixtures=ACTION_FIXTURES)
    report = evaluate(client, ACCEPTANCE_CASES[:args.limit]);report['provider'] = 'live DeepSeek' if args.live else 'mock exact fixtures (not live accuracy)'
    from src.trip_action_rendering import safe_trace
    report = safe_trace(report)
    if args.json:print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('Provider:', report['provider'])
        for row in report['cases']:
            print(row['status'], '|', row['text'])
            print('  expected:', [a['action_type'] for a in row['expected']['actions']])
            print('  actual:', [a['action_type'] for a in row['actual']['actions']] if row['actual'] else row.get('error'))
            if row['actual']:print('  targets:', [a['target_mentions'] for a in row['actual']['actions']])
        print('Core:', report['core_pass_rate'], '| Complex:', report['complex_pass_rate'], '| Thresholds:', report['thresholds_passed'])
    return 0 if report['passed'] == report['case_count'] else 1


if __name__ == '__main__':raise SystemExit(main())

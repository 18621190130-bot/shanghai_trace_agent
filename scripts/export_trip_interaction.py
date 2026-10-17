"""Export offline interaction evidence. Never calls a live provider."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.demos.trip_agent_demo import build_agent, full_journey
from tools.evaluation.nlu_live_eval import evaluate
from src.llm_client import MockLLMClient
from src.poi_repository import POIRepository
from src.trip_actions import action_schema
from src.trip_action_fixtures import ACTION_FIXTURES, ACCEPTANCE_CASES, action, utterance
from src.trip_agent_fixtures import FULL_JOURNEY_INITIAL


def main():
    output = ROOT / 'examples' / 'trip_interaction'
    output.mkdir(exist_ok=True)
    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = evaluate(MockLLMClient(fixtures=ACTION_FIXTURES))
    report['provider'] = 'mock exact fixtures (not live accuracy)'
    report['live_api_calls'] = 0
    save('nlu_mock_eval.json', report)
    save('action_schema.json', action_schema(POIRepository()))
    save('acceptance_cases.json', ACCEPTANCE_CASES)
    save('full_journey.json', full_journey())
    scenarios = []
    for name, commands in (
        ('skip_no_refill', [('Skip this place.', None)]),
        ('named_remove', [('Add West Bund Museum.', action('ADD_PLACE', target_mentions=['West Bund Museum'])),
                          ("I don't want to go to West Bund Museum anymore.", None)]),
        ('soft_add_preserves', [('Remove Long Museum.', action('REMOVE_PLACE', target_mentions=['Long Museum'])),
                                ('I only have one hour left.', None), ('Add Long Museum to my route.', None)]),
        ('revisit_not_noop', [("I've finished this stop.", None), ('I want to visit TANK Shanghai again.', None)]),
    ):
        agent = build_agent();sid = agent.create_session().session_id
        agent.handle_turn(sid, FULL_JOURNEY_INITIAL);agent.handle_turn(sid, 'start')
        def state():return agent.trip_store.get(agent.sessions.get(sid).trip_id).to_dict()
        turns = []
        for text, proposal in commands:
            before = state()
            if proposal:agent.client.responses = [utterance(proposal)]
            result = agent.handle_turn(sid, text).to_dict()
            turns.append(dict(user_text=text, proposal_source='explicit offline proposal' if proposal else 'exact mock fixture',
                              before=before, result=result, after=state()))
        scenarios.append(dict(name=name, turns=turns))
    save('regression_cases.json', dict(provider='mock', live_api_calls=0, scenarios=scenarios))
    baseline = json.loads((output / 'protected_before.json').read_text(encoding='utf-8'))
    changed = [p for p, old in baseline.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != old]
    allowed = ['src\\trip_state.py', 'src\\trip_store.py', 'src\\trip_replanning.py',
               'src\\trip_conversation.py', 'src\\trip_agent.py', 'src\\trip_agent_fixtures.py']
    digest = hashlib.sha256((ROOT / 'data' / 'pois.json').read_bytes()).hexdigest()
    checks = dict(baseline_file_count=len(baseline), changed_existing_files=changed,
                  allowed_existing_changes=allowed, unexpected_changes=[p for p in changed if p not in allowed],
                  production_sha256=digest, production_count=len(POIRepository().get_all_pois()),
                  live_api_calls=0)
    save('protected_checks.json', checks)
    assert not checks['unexpected_changes'], checks
    assert digest == '6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782'
    assert report['passed'] == 58 and report['thresholds_passed']
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print('Offline corpus: 58/58. This is not measured live NLU accuracy.')


if __name__ == '__main__':main()

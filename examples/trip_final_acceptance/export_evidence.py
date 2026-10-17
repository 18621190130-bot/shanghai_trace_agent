"""Offline Phase 3A-4.2 evidence; never calls a live provider."""
import ast
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trip_agent_demo import build_agent
from src.trip_agent_fixtures import FULL_JOURNEY_INITIAL
from src.trip_action_fixtures import ACTION_FIXTURES, ACCEPTANCE_CASES, action, utterance
from src.llm_client import MockLLMClient
from nlu_live_eval import evaluate


def main():
    folder = Path(__file__).parent
    def save(name, value):folder.joinpath(name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report = evaluate(MockLLMClient(fixtures=ACTION_FIXTURES))
    report.update(provider='mock exact fixtures; not live accuracy', live_api_calls=0)
    save('nlu_mock_eval.json', report);save('acceptance_cases.json', ACCEPTANCE_CASES)
    assert report['passed'] == len(ACCEPTANCE_CASES) and report['thresholds_passed']
    results = []
    for name, kind, minutes, text, must in (
        ('remaining_hard_60', 'SET_HARD_TIME_LIMIT', 60, 'I only have one hour left.', False),
        ('preferred_soft_60', 'SET_TIME_TARGET', 60, "I'd like to spend about another hour, but there's no rush.", False),
        ('ordinary_hard_30', 'SET_HARD_TIME_LIMIT', 30, 'I must leave in 30 minutes.', False),
        ('must_go_conflict_20', 'SET_HARD_TIME_LIMIT', 20, 'I only have 20 minutes left.', True),
    ):
        agent = build_agent();sid = agent.create_session().session_id
        agent.handle_turn(sid, FULL_JOURNEY_INITIAL);agent.handle_turn(sid, 'start')
        if must:
            agent.client.responses = [utterance(action('ADD_MUST_GO', target_mentions=['Long Museum']))]
            agent.handle_turn(sid, 'Long Museum is a must-go.')
        tid = agent.sessions.get(sid).trip_id;before = agent.trip_store.get(tid).to_dict()
        agent.client.responses = [utterance(action(kind, time_value_minutes=minutes))]
        result = agent.handle_turn(sid, text).to_dict();after = agent.trip_store.get(tid).to_dict()
        results.append(dict(case=name, text=text, proposal_source='explicit offline semantic proposal', before=before, result=result, after=after))
    save('final_cases.json', dict(provider='mock', live_api_calls=0, cases=results))
    baseline = json.loads(folder.joinpath('protected_before.json').read_text(encoding='utf-8'))
    changed = [p for p, old in baseline.items() if hashlib.sha256(ROOT.joinpath(p).read_bytes()).hexdigest() != old]
    allowed = {str(Path('src')/p) for p in ('trip_actions.py','trip_action_fixtures.py','trip_action_executor.py','route_mutation.py','trip_action_rendering.py')}
    tree = ast.parse(ROOT.joinpath('src/route_mutation.py').read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name=='compress')
    compression = ast.dump(node, include_attributes=False)
    digest = hashlib.sha256(ROOT.joinpath('data/pois.json').read_bytes()).hexdigest()
    checks = dict(baseline_file_count=len(baseline), changed_existing_files=changed,
                  unexpected_changes=[p for p in changed if p not in allowed],
                  compression_ast_unchanged=compression==folder.joinpath('compression_before.txt').read_text(encoding='utf-8'),
                  compression_ast_sha256=hashlib.sha256(compression.encode()).hexdigest(),
                  production_sha256=digest, live_api_calls=0)
    save('protected_checks.json', checks)
    assert not checks['unexpected_changes'] and checks['compression_ast_unchanged']
    assert digest == '6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782'
    print(json.dumps(checks, indent=2));print('Mock corpus:',report['passed'],'/',report['case_count'])


if __name__ == '__main__':main()

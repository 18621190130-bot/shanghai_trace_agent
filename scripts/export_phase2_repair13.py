"""Reproducible final-repair evidence; fixture parsing is explicitly not live."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.demos.route_entry_demo import main
from src import POIRepository, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES, candidate


def cli(repo, fixtures, text, answers):
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch('tools.demos.route_entry_demo.POIRepository', return_value=repo), \
            patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=MockLLMClient(fixtures=fixtures)), \
            patch('sys.stdin', io.StringIO(answers)), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(['--mode', 'plan_for_me', '--text', text], live=True)
    assert code == 0, stderr.getvalue()
    return stdout.getvalue()


def export():
    specs = [('A', "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.", None),
             ('B', 'I want to see the more authentic side of Shanghai.', '3'),
             ('C', 'I have two hours and want architecture and local neighborhoods.', None)]
    fixtures = dict(PLAN_EXAMPLES)
    # Reproduce the actual reported supporting-preference variant explicitly.
    fixtures[specs[1][1]] = candidate(interest_tags=['local_life'], experience_tags=['local_atmosphere'])
    fixtures[specs[2][1]] = candidate(available_minutes=120, interest_tags=['architecture', 'local_life'],
                                    experience_tags=['neighborhood_walk'])
    repo = POIRepository()
    service = RouteEntryService(repo, MockLLMClient(fixtures=fixtures))
    cases, transcripts, live_attempts = {}, [], []
    for name, text, answer in specs:
        initial = service.parse_plan(text)
        intent = initial if answer is None else service.answer_clarification(initial, 'available_minutes', answer)
        result = service.generate(intent)
        assert result.status == 'success'
        assert result.route_quality.status == 'passed'
        assert 'p33' not in [p.poi_id for p in result.route_plan.ordered_pois]
        cases[name] = dict(input=text, clarification=answer, initial_intent=initial.to_dict(), final=result.to_dict())
        transcripts.append(f'CASE {name}\nMock provider injected; actual CLI flow\n' +
                           cli(repo, fixtures, text, '' if answer is None else answer+'\n'))
        argv = ['--mode', 'plan_for_me', '--text', text]
        run = subprocess.run([sys.executable, 'tools/demos/chat_demo.py', *argv], cwd=ROOT,
            input='' if answer is None else answer+'\n', capture_output=True, text=True, encoding='utf-8',
            timeout=60, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        live_attempts.append(dict(case=name, argv=['python', 'tools/demos/chat_demo.py', *argv], returncode=run.returncode,
                                  stdout=run.stdout, stderr=run.stderr))
    # Explicitly synthetic restricted catalog exercises both adaptive branches.
    raw = repo.get_raw_data()
    raw['pois'] = [p for p in raw['pois'] if p['id'] == 'p2']
    raw['pois'][0]['display_order'] = 1
    raw['metadata']['poi_count'] = 1
    for zone in raw['metadata']['walk_zones']:
        zone['poi_count'] = int(zone['id'] == raw['pois'][0]['walk_zone']['id'])
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'pois.json'
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        sparse_repo = POIRepository(path)
        for name, choice in [('SYNTHETIC_KEEP_STRICT', '1'), ('SYNTHETIC_BROADEN', '2')]:
            sparse_service = RouteEntryService(sparse_repo, MockLLMClient(fixtures=fixtures))
            initial = sparse_service.parse_plan(specs[1][1])
            complete = sparse_service.answer_clarification(initial, 'available_minutes', '3')
            pending = sparse_service.generate(complete)
            assert pending.status == 'needs_route_quality_clarification'
            final = sparse_service.answer_route_quality_clarification(pending, choice)
            assert final.status == 'success' and final.route_quality.clarification_applied
            cases[name] = dict(execution='Synthetic one-POI catalog, not the production inventory',
                               pending=pending.to_dict(), choice=choice, final=final.to_dict())
            transcripts.append(name+'\nSYNTHETIC ONE-POI CATALOG + MOCK PARSING\n'+
                               cli(sparse_repo, fixtures, specs[1][1], '3\n'+choice+'\n'))
    output = ROOT/'examples'/'phase2'
    (output/'phase2_repair13.json').write_text(json.dumps(dict(
        execution='Actual shared-engine and CLI execution with explicitly injected Mock parsing; not live semantic verification.',
        cases=cases, live_cli_attempts=live_attempts), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'phase2_repair13_cli.txt').write_text('OFFLINE MOCK PARSING — actual CLI flow\n\n'+
        '\n\n'.join(transcripts)+'\n\nREAL tools/demos/chat_demo.py ATTEMPTS\n'+
        json.dumps(live_attempts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for name, case in cases.items():
        final = case['final']
        plan = final['route_plan']
        print(name, final['status'], [(p['poi_id'], p['selection_reason'], round(p['recommendation_score'],3))
                                     for p in plan['ordered_pois']],
              {k: plan[k] for k in ('total_estimated_minutes', 'remaining_minutes', 'time_utilization_ratio',
                                    'estimated_max_single_leg_km', 'richness_target_met')}, final['route_quality']['status'])
    print('Live CLI return codes:', [r['returncode'] for r in live_attempts])
    print('Provider key present:', bool(os.environ.get('DEEPSEEK_API_KEY')))


if __name__ == '__main__':
    export()

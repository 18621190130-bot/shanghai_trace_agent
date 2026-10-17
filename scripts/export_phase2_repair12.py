"""Repair 1.2 outputs: distinguish live CLI attempts from fixture-based execution."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.demos.route_entry_demo import main
from src import POIRepository, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES, candidate


def export():
    specs = [('A', "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.", None),
             ('B', 'I want to see the more authentic side of Shanghai.', '3'),
             ('C', 'I have two hours and want architecture and local neighborhoods.', None)]
    fixtures = dict(PLAN_EXAMPLES)
    fixtures[specs[2][1]] = candidate(available_minutes=120, interest_tags=['architecture', 'local_life'],
                                    experience_tags=['neighborhood_walk'])
    service = RouteEntryService(POIRepository(), MockLLMClient(fixtures=fixtures))
    cases, transcripts, live_attempts = {}, [], []
    for name, text, answer in specs:
        initial = service.parse_plan(text)
        intent = initial if answer is None else service.answer_clarification(initial, 'available_minutes', answer)
        result = service.generate(intent)
        assert result.status == 'success'
        assert 'p33' not in [p.poi_id for p in result.route_plan.ordered_pois]
        cases[name] = dict(input=text, clarification=answer, initial_intent=initial.to_dict(), final=result.to_dict())
        argv = ['--mode', 'plan_for_me', '--text', text]
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=MockLLMClient(fixtures=fixtures)), \
                patch('sys.stdin', io.StringIO('' if answer is None else answer+'\n')), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv, live=True)
        assert code == 0, stderr.getvalue()
        transcripts.append(f'CASE {name}\nOffline fixture injected at Provider seam; actual live-entry CLI flow\n'
                           f'Input: {text}\nClarification: {answer}\n{stdout.getvalue()}')
        run = subprocess.run([sys.executable, 'tools/demos/chat_demo.py', *argv], cwd=ROOT,
            input='' if answer is None else answer+'\n', capture_output=True, text=True, encoding='utf-8',
            timeout=60, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        live_attempts.append(dict(case=name, argv=['python', 'tools/demos/chat_demo.py', *argv], returncode=run.returncode,
                                  stdout=run.stdout, stderr=run.stderr))
    output = ROOT/'examples'/'phase2'
    (output/'phase2_repair12.json').write_text(json.dumps(dict(
        execution='Actual shared-engine and CLI execution with explicitly injected Mock parsing; not live semantic verification.',
        cases=cases, live_cli_attempts=live_attempts), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'phase2_repair12_cli.txt').write_text('OFFLINE MOCK PARSING — actual CLI flow\n\n'+
        '\n\n'.join(transcripts)+'\n\nREAL tools/demos/chat_demo.py ATTEMPTS\n'+
        json.dumps(live_attempts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for name, case in cases.items():
        plan = case['final']['route_plan']
        print(name, [(p['poi_id'], p['selection_reason'], round(p['recommendation_score'],3))
                     for p in plan['ordered_pois']],
              {k: plan[k] for k in ('total_estimated_minutes', 'remaining_minutes', 'time_utilization_ratio',
                                    'estimated_max_single_leg_km', 'richness_target_met')})
    print('Live CLI return codes:', [r['returncode'] for r in live_attempts])
    print('Provider key present:', bool(os.environ.get('DEEPSEEK_API_KEY')))


if __name__ == '__main__':
    export()

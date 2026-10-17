"""Reproduce Repair 1.1 regressions with explicitly offline fixture parsing."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import POIRepository, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES


def export():
    service = RouteEntryService(POIRepository(), MockLLMClient(fixtures=PLAN_EXAMPLES))
    cases, transcripts = {}, []
    specs = [('A', "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.", None),
             ('B', 'I want to see the more authentic side of Shanghai.', '3 hours')]
    for name, text, answer in specs:
        initial = service.parse_plan(text)
        intent = initial if answer is None else service.answer_clarification(initial, 'available_minutes', answer)
        result = service.generate(intent)
        assert result.status == 'success'
        cases[name] = dict(input=text, clarification=answer, initial_intent=initial.to_dict(), final=result.to_dict())
        run = subprocess.run([sys.executable, 'tools/demos/route_entry_demo.py', '--mode', 'plan_for_me', '--text', text],
            input='' if answer is None else answer+'\n', cwd=ROOT, capture_output=True, text=True,
            encoding='utf-8', timeout=30, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        assert run.returncode == 0, run.stderr
        transcripts.append(f'CASE {name}\nInput: {text}\nClarification: {answer}\n{run.stdout}')
    output = ROOT / 'examples' / 'phase2'
    (output/'phase2_repair11.json').write_text(json.dumps(dict(
        execution='Actual engine and CLI execution; initial parsing uses offline Mock fixtures, not live DeepSeek.',
        live_provider_executed=False, cases=cases), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'phase2_repair11_cli.txt').write_text(
        'OFFLINE MOCK PARSING — actual CLI transcripts\n\n'+'\n\n'.join(transcripts), encoding='utf-8')
    for name, case in cases.items():
        plan = case['final']['route_plan']
        print(name, [(p['poi_id'], p['recommendation_score']) for p in plan['ordered_pois']],
              {k: plan[k] for k in ('total_estimated_minutes', 'remaining_minutes', 'time_utilization_ratio',
                                    'estimated_max_single_leg_km')})
    print('Provider key present:', bool(os.environ.get('DEEPSEEK_API_KEY')))


if __name__ == '__main__':
    export()

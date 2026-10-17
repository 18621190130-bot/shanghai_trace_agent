"""Actual engine/CLI simulation with explicitly supplied Mock semantic responses."""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.demos.route_entry_demo import main
from src import POIRepository, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from src.intent_schema import candidate_schema, route_intent_schema

WEST = "I have three hours for a city walk in the west bund and I'm more interested in art and natural scenery and I don't like museums."


def export():
    rng = random.Random(20261004)
    specs = [
        ('A', WEST, candidate(available_minutes=180, interest_tags=['art', 'parks'], preferred_zone='west_bund', avoid_tags=['museum_visit']), [], 'industrial_heritage'),
        ('B', "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.", candidate(available_minutes=150, interest_tags=['local_life'], experience_tags=['neighborhood_walk'], avoid_tags=['museum_visit']), [], 'strict'),
        ('C', 'I want to see the more authentic side of Shanghai.', candidate(interest_tags=['local_life'], experience_tags=['local_atmosphere']), [('available_minutes', '3')], 'strict'),
    ]
    variations = [
        ('literary', ['I have two hours in Hongkou and would enjoy literature and a quiet walk.',
                     "A quiet literary walk in Hongkou sounds nice; I've got two hours."],
         candidate(available_minutes=120, interest_tags=['literature'], experience_tags=['quiet_walk'], preferred_zone='hongkou_literary'), 'architecture'),
        ('short_local', ["I've only got thirty minutes; show me some ordinary local neighborhood life.",
                         'I have half an hour for a short walk through local neighborhoods.'],
         candidate(available_minutes=30, interest_tags=['local_life'], experience_tags=['neighborhood_walk']), 'strict'),
        ('shopping', ['I have two and a half hours near Nanjing Road for shopping and modern city life.',
                      "Shopping and modern Shanghai interest me; I've got 150 minutes around Nanjing Road."],
         candidate(available_minutes=150, interest_tags=['shopping_lifestyle', 'modern_city'], preferred_zone='old_city_central'), 'strict'),
        ('must_go', ['I have two hours for architecture and local life, and I definitely want to see Wukang Mansion.',
                     'Please include Wukang Mansion in a two-hour architecture and local-neighborhood walk.'],
         candidate(available_minutes=120, interest_tags=['architecture', 'local_life'], must_go_place_names=['Wukang Mansion']), 'strict'),
        ('museum_deep', ["I have three hours in the West Bund; I'd like an in-depth art museum visit.",
                         'For three hours in the West Bund, I want to take my time with art exhibitions.'],
         candidate(available_minutes=180, interest_tags=['art'], experience_tags=['museum_visit'], travel_pace='deep', preferred_zone='west_bund'), 'strict'),
        ('zero_art', ["I have three hours in the West Bund. I'm interested only in art, but no museums, please.",
                      "Art is my main interest for three hours in the West Bund; I'd rather avoid museums."],
         candidate(available_minutes=180, interest_tags=['art'], preferred_zone='west_bund', avoid_tags=['museum_visit']), 'waterfront'),
        ('broaden_area', ['I have three hours in the West Bund and want ordinary local neighborhoods, not museums.',
                          "Local neighborhood life is what I'd like in the West Bund for three hours; please skip museums."],
         candidate(available_minutes=180, interest_tags=['local_life'], experience_tags=['local_atmosphere'], preferred_zone='west_bund', avoid_tags=['museum_visit']), 'broaden_area'),
        ('parks', ['I have ninety minutes in Hongkou for parks and a quiet walk.',
                   'A quiet park walk in Hongkou for an hour and a half would suit me.'],
         candidate(available_minutes=90, interest_tags=['parks'], experience_tags=['quiet_walk'], preferred_zone='hongkou_literary'), 'strict'),
    ]
    specs += [('SIM_'+name, rng.choice(texts), payload, [], choice) for name, texts, payload, choice in variations]
    repo = POIRepository()
    cases, transcripts = {}, []
    for name, text, payload, missing_answers, desired_choice in specs:
        service = RouteEntryService(repo, MockLLMClient(fixtures={text: payload}))
        intent = service.parse_plan(text)
        initial = intent.to_dict()
        for field, answer in missing_answers:
            intent = service.answer_clarification(intent, field, answer)
        pending = service.generate(intent)
        final, quality_choice = pending, None
        if pending.status == 'needs_route_quality_clarification':
            values = [o.value for o in pending.route_quality.options]
            quality_choice = desired_choice if desired_choice in values else 'strict'
            final = service.answer_route_quality_clarification(pending, quality_choice)
        cases[name] = dict(input=text, fixture=payload, initial_intent=initial, missing_answers=missing_answers,
                           pending=pending.to_dict(), quality_answer=quality_choice, final=final.to_dict())
        stdout, stderr = io.StringIO(), io.StringIO()
        answers = [answer for _, answer in missing_answers] + ([quality_choice] if quality_choice else [])
        with patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=MockLLMClient(fixtures={text: payload})), \
                patch('sys.stdin', io.StringIO('\n'.join(answers)+'\n')), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['--mode', 'plan_for_me', '--text', text], live=True)
        assert code == (0 if final.status == 'success' else 1), stderr.getvalue()
        transcripts.append(name+'\nNATURAL LANGUAGE: '+text+'\nANSWERS: '+repr(answers)+'\n'+stdout.getvalue())
    attempts = []
    for name, text, _, missing_answers, _ in specs[:3]:
        argv = [sys.executable, 'tools/demos/chat_demo.py', '--mode', 'plan_for_me', '--text', text]
        run = subprocess.run(argv, cwd=ROOT, input='\n'.join([a for _, a in missing_answers]+['strict'])+'\n',
            capture_output=True, encoding='utf-8', timeout=60, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        attempts.append(dict(case=name, argv=argv, returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
    examples = ROOT/'examples'/'phase2'
    (examples/'phase2_unified_patch.json').write_text(json.dumps(dict(
        execution='Mock semantic responses explicitly supplied for each input; actual expansion, engine and CLI execution.',
        seed=20261004, cases=cases, live_cli_attempts=attempts), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (examples/'phase2_unified_patch_cli.txt').write_text('MOCK PARSING — NOT LIVE SEMANTIC ACCURACY EVIDENCE\n\n'+
        '\n\n'.join(transcripts)+'\nREAL CLI ATTEMPTS\n'+json.dumps(attempts,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    lines = ['# Plan for me：自然语言与实际模拟输出', '',
             '措辞使用固定随机种子20261004生成。语义解析使用逐条明确编写的Mock响应；实际执行Semantic Expansion、共享引擎、一次澄清及CLI。不能证明真实LLM理解了这些措辞。', '',
             '| Case | Initial stops / status | Quality answer | Final status / stops |', '| --- | --- | --- | --- |']
    for name, case in cases.items():
        initial, final = case['pending'], case['final']
        lines.append(f"| {name} | {len((initial['route_plan'] or {}).get('ordered_pois', []))} / {initial['status']} | {case['quality_answer'] or '—'} | {final['status']} / {len((final['route_plan'] or {}).get('ordered_pois', []))} |")
    for name, case in cases.items():
        lines += ['', '## '+name, '', '**自然语言：** '+case['input'], '',
                  '**缺字段回答：** '+repr(case['missing_answers']), '',
                  '**质量澄清回答：** '+str(case['quality_answer'] or '没有触发'), '', '```text',
                  next(t for t in transcripts if t.startswith(name+'\n')), '```']
    (examples/'phase2_plan_for_me_simulations.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    for filename, schema in [('llm_candidate.schema.json', candidate_schema(repo)), ('route_intent.schema.json', route_intent_schema(repo))]:
        (examples/filename).write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (examples/'intent_system_prompt.txt').write_text(RouteEntryService(repo,MockLLMClient()).parser.system_prompt(),encoding='utf-8')
    for name, case in cases.items():
        final = case['final']; plan = final['route_plan']
        print(name, case['pending']['status'], '->', case['quality_answer'], '->', final['status'],
              [(n['poi_id'], n['name_en']) for n in (plan or {}).get('ordered_pois', [])],
              (plan or {}).get('total_estimated_minutes'))
    print('Live CLI return codes:', [r['returncode'] for r in attempts])


if __name__ == '__main__':
    export()

"""Real provider CLI traces; never supplies Mock responses or records API keys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "Shopping and modern Shanghai interest me; I've got 150 minutes around Nanjing Road.",
    'For three hours in the West Bund, I want to take my time with art exhibitions.',
    'I have three hours in the West Bund and want ordinary local neighborhoods, not museums.',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    label = 'baseline' if args.baseline else 'smoke'
    records = []
    for text in CASES[:1] if args.baseline else CASES:
        env = {**os.environ, 'DEEPSEEK_DEBUG': '1', 'PYTHONIOENCODING': 'utf-8'}
        command = [sys.executable, 'tools/demos/chat_demo.py', '--mode', 'plan_for_me', '--text', text]
        # Nanjing Road is not a zone alias in the frozen resolver. Answer the
        # existing start-area question, then keep preferences at quality review.
        answers = '2\nstrict\n' if text == CASES[0] and not args.baseline else 'strict\n'
        try:
            run = subprocess.run(command, input=answers, cwd=ROOT, capture_output=True,
                                 text=True, encoding='utf-8', timeout=90, env=env)
            stdout, stderr, code = run.stdout, run.stderr, run.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b''
            stderr = exc.stderr or b''
            stdout = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr
            code = None
        # Defense in depth in case an external provider echoes a credential.
        key = os.environ.get('DEEPSEEK_API_KEY')
        if key:
            stdout, stderr = stdout.replace(key, '[REDACTED]'), stderr.replace(key, '[REDACTED]')
        diagnostics = []
        for line in stderr.splitlines():
            try:
                diagnostics.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        record = dict(input=text, clarification_answers=answers.splitlines(), returncode=code, stdout=stdout, stderr=stderr,
                      diagnostics=diagnostics, parsed_intent_reached='Parsed Intent' in stdout,
                      route_flow_reached='Route Quality Check:' in stdout)
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    (ROOT/'examples'/'phase2'/f'deepseek_provider_{label}.json').write_text(
        json.dumps(dict(execution='REAL DeepSeek CLI subprocess calls, no Mock client', cases=records),
                   ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if not args.baseline and not all(r['parsed_intent_reached'] and r['route_flow_reached'] for r in records):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Reproducible frozen-layer SHA audit; no network and no regression rerun."""
import hashlib
import json
from pathlib import Path
from src import POIRepository

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'examples/weather_reality'
ALLOWED_EXISTING = {'src/services/world_context_service.py','src/services/opening_hours.py'}


def audit():
    baseline = json.loads((OUT/'phase3b_3_baseline_manifest.json').read_text(encoding='utf-8'))['files']
    files = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for base in ('src','tests','scripts','data') for p in sorted((ROOT/base).rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    changed = sorted(k for k,v in baseline.items() if files.get(k) != v)
    assert set(changed) <= ALLOWED_EXISTING, changed
    repo = POIRepository(); assert len(repo.get_all_pois()) == 58
    result = dict(phase='3B_4',baseline_file_count=len(baseline),current_file_count=len(files),
                  changed_existing_files=changed,new_files=sorted(set(files)-set(baseline)),
                  all_other_frozen_files_unchanged=True,core_count=58,
                  core_sha256=files['data/pois.json'],files=files)
    (OUT/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False,indent=2))
    return result


if __name__ == '__main__':
    audit()

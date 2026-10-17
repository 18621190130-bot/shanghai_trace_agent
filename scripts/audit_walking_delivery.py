"""Audit frozen protections and known configured-secret exposure without printing values."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'examples/phase3a_freeze/manifest.json').read_text(encoding='utf-8'))
    changed = [name for name, value in manifest.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
    protected = ['src/route_engine.py', 'src/geo_utils.py', 'data/pois.json',
                 'src/trip_state.py', 'src/trip_store.py', 'src/trip_commands.py', 'src/intent_models.py']
    failed = [name for name in protected if name in changed]
    old_tests_changed = [name for name in changed if name.startswith('tests/')]
    secrets = [v.encode() for k, v in os.environ.items()
               if k in ('AMAP_API_KEY', 'AMAP_WEB_SERVICE_KEY', 'DEEPSEEK_API_KEY') and len(v) >= 16]
    exposed = []
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.py', '.md', '.txt', '.json', '.example') and '__pycache__' not in path.parts:
            data = path.read_bytes()
            if any(secret in data for secret in secrets):
                exposed.append(path.relative_to(ROOT).as_posix())
    with ZipFile(ROOT / 'examples/phase3a_freeze/phase3a_baseline.zip') as archive:
        archive_exposed = [name for name in archive.namelist() if any(s in archive.read(name) for s in secrets)]
    result = dict(protected_files_unchanged=not failed, protected_failures=failed,
                  old_test_files_unchanged=not old_tests_changed, old_tests_changed=old_tests_changed,
                  changed_baseline_files=changed, configured_secret_exposures=exposed,
                  frozen_archive_configured_secret_exposures=archive_exposed,
                  secret_scan_scope='Known configured environment credentials, not a universal secret scanner')
    output = ROOT / 'examples/walking_routing/delivery_audit.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed or old_tests_changed or exposed or archive_exposed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

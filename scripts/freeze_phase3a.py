"""Preserve an unversioned Phase 3A baseline without archiving credentials."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]

def main():
    out = ROOT / 'examples/phase3a_freeze'
    out.mkdir(exist_ok=True)
    archive = out / 'phase3a_baseline.zip'
    if archive.exists():
        raise SystemExit('Baseline already exists; refusing to overwrite')
    paths = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and p.suffix in ('.py', '.json', '.md', '.txt')
                   and '__pycache__' not in p.parts
                   and not any(x in p.parts for x in ('.git', 'examples')))
    manifest = {}
    with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
        for p in paths:
            name = p.relative_to(ROOT).as_posix()
            manifest[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            bundle.write(p, name)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Frozen files:', len(manifest))

if __name__ == '__main__':
    main()

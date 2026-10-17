"""Build a credentials-free review snapshot, without claiming owner acceptance."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    paths=set()
    for folder in ('src','scripts','tests','data','docs','examples/spatial_identity','examples/location_awareness','examples/walking_routing'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.json','.md','.txt','.csv','.example'):
                paths.add(path)
    for name in ('PHASE3B_2_REPORT.md','PHASE3B_2_1_REPORT.md','PHASE3B_2_2_REPORT.md','PHASE3B_2_FREEZE.md','SPATIAL_PROFILE_REVIEW.md','README.md'):
        path=ROOT/name
        if path.exists():paths.add(path)
    out=ROOT/'examples/phase3b_2_freeze_candidate';out.mkdir(exist_ok=True)
    archive=out/'phase3b_2_candidate.zip'
    hashes={}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            relative=path.relative_to(ROOT).as_posix();data=path.read_bytes()
            hashes[relative]=hashlib.sha256(data).hexdigest();z.writestr(relative,data)
    manifest=dict(status='READY_PENDING_HUMAN_ACCEPTANCE',phase='3B_2',file_count=len(hashes),
                  archive=archive.name,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=hashes)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=manifest['status'],files=len(hashes),archive_bytes=archive.stat().st_size),indent=2))


if __name__=='__main__':main()

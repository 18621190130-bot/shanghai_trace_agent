"""Run from project root; online requests occur only with --live."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.poi_pipeline.collection import collect_sources, write_outputs
from src.poi_pipeline.sources.base import CachedHTTP
from src.poi_pipeline.sources.amap_source import AmapSource
from src.poi_pipeline.sources.osm_source import OSMSource
from src.poi_pipeline.sources.official_source import OfficialSource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow real HTTP; otherwise cache replay only")
    parser.add_argument("--retry-failed", action="store_true", help="Retry cached transport failures with --live")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "poi_pipeline")
    args = parser.parse_args()
    kb = ROOT / "data" / "pois.json"
    before = hashlib.sha256(kb.read_bytes()).hexdigest()
    http = CachedHTTP(args.output / "cache", offline=not args.live, retry_failed=args.retry_failed)
    result = collect_sources([AmapSource(http), OSMSource(http), OfficialSource(http)])
    result[3]["production_unchanged"] = hashlib.sha256(kb.read_bytes()).hexdigest() == before
    result[3]["production_sha256"] = before
    write_outputs(args.output, *result)
    print(json.dumps({k: result[3][k] for k in ("counts", "raw_source_coverage", "partial_source_failure", "production_unchanged")}, ensure_ascii=True))


if __name__ == "__main__":
    main()

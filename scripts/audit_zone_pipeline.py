"""Read-only KB preflight; does not claim to run the unfinished full pipeline."""
import argparse
import hashlib
import json
from pathlib import Path

from src.poi_repository import POIRepository
from src.poi_pipeline.coverage import ZoneCoverageAnalyzer
from src.poi_pipeline.boundary import POLYGON, REVIEW_MARGIN_M
from src.poi_pipeline.zone_config import ZonePipelineConfig

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT):
    candidate = root / 'data/pois_phase2_5_candidate.json'
    production = root / 'data/pois.json'
    repo = POIRepository(candidate)
    output = root / 'data/poi_pipeline/all_zones'
    output.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    zones = []
    for zone in repo._raw['metadata']['walk_zones']:
        zid = zone['id']
        baseline = ZoneCoverageAnalyzer(zid, repo).analyze()
        baseline['audit_input'] = str(candidate.relative_to(root))
        write(f'{zid}_baseline_report.json', baseline)
        config=ZonePipelineConfig.load(zid)
        zones.append(dict(zone_id=zid, display_name=zone['name_zh'],
            boundary=config.polygon,
            boundary_review_margin=config.boundary_review_margin_m,
            boundary_status=config.settings['initial_product_boundary'],
            seed_production_pois=[p['id'] for p in json.loads(production.read_text(encoding='utf-8-sig'))['pois'] if p['walk_zone']['id'] == zid],
            poi_count=baseline['poi_count']))
    protected = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (production, candidate)}
    report = dict(status='BOUNDARIES_READY', completed_zones=['west_bund'],
        completed_zones_note='West Bund completion inherited from Phase 2.5C; no discovery rerun.',
        blocked_zones=[z['zone_id'] for z in zones if z['boundary'] is None],
        blocker=None,
        zone_preflight=zones, protected_sha256=protected,
        collection_attempted=False, enrichment_attempted=False, deepseek_calls=0,
        route_regression_status='not_run', promotion_ready=False,
        cost_note='No collection or enrichment performed; zero calls do not demonstrate marginal-cost improvement.')
    write('preflight_report.json', report)
    return report


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(audit(), ensure_ascii=False, indent=2))

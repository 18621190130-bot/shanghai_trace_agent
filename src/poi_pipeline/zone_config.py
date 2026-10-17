"""Explicit product configuration; no inferred administrative or seed-box boundary."""
from dataclasses import dataclass
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2]/'data/poi_pipeline/zone_configs.json'

@dataclass(frozen=True)
class ZonePipelineConfig:
    zone_id: str
    display_name: str
    polygon: tuple
    boundary_review_margin_m: float
    seed_production_pois: tuple
    discovery_terms: tuple
    official_source_targets: tuple
    allowed_candidate_categories: tuple
    excluded_generic_categories: tuple
    settings: dict

    @property
    def bounds(self):
        return (min(p[0] for p in self.polygon), min(p[1] for p in self.polygon),
                max(p[0] for p in self.polygon), max(p[1] for p in self.polygon))

    @classmethod
    def load(cls, zone_id, path=CONFIG_PATH):
        rows=json.loads(Path(path).read_text(encoding='utf-8'))
        row=next((r for r in rows if r['zone_id']==zone_id),None)
        if row is None: raise ValueError('Unknown zone: '+zone_id)
        return cls(zone_id,row['display_name'],tuple(tuple(p) for p in row['polygon']),
            row['boundary_review_margin_m'],tuple(row['seed_production_pois']),tuple(row['discovery_terms']),
            tuple(row['official_source_targets']),tuple(row['allowed_candidate_categories']),
            tuple(row['excluded_generic_categories']),row)

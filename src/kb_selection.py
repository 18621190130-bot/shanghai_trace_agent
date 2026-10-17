"""Explicit CLI KB selection. Never detect or promote a candidate automatically."""
from pathlib import Path
from .poi_repository import POIRepository

KB_NAMES = ('production', 'phase2_5_candidate', 'phase2_5_all_zones_candidate', 'phase2_5_recall_candidate', 'phase2_5_diversity_candidate')
CANDIDATE_PATH = Path(__file__).resolve().parents[1] / 'data/pois_phase2_5_candidate.json'
ALL_ZONES_CANDIDATE_PATH = Path(__file__).resolve().parents[1] / 'data/pois_phase2_5_all_zones_candidate.json'
RECALL_CANDIDATE_PATH = Path(__file__).resolve().parents[1] / 'data/pois_phase2_5_recall_candidate.json'
DIVERSITY_CANDIDATE_PATH = Path(__file__).resolve().parents[1] / 'data/pois_phase2_5_diversity_candidate.json'


def resolve_poi_repository(kb_name='production', *, repository_factory=None):
    factory = repository_factory or POIRepository
    if kb_name == 'production':
        return factory()
    if kb_name == 'phase2_5_candidate':
        return factory(CANDIDATE_PATH)
    if kb_name == 'phase2_5_all_zones_candidate':
        return factory(ALL_ZONES_CANDIDATE_PATH)
    if kb_name == 'phase2_5_recall_candidate':
        return factory(RECALL_CANDIDATE_PATH)
    if kb_name == 'phase2_5_diversity_candidate':
        return factory(DIVERSITY_CANDIDATE_PATH)
    raise ValueError('Unknown POI KB: ' + str(kb_name))


def kb_summary(kb_name, repository):
    return {'POI KB': kb_name, 'POI Count': len(repository.get_all_pois()),
            'West Bund Route Nodes': sum(p.counts_as_route_stop for p in repository.get_pois_by_zone('west_bund'))}


def render_kb_summary(summary):
    return '\n'.join(f'{label}: {value}' for label, value in summary.items())

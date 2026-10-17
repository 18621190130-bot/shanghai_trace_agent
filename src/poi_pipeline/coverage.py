from collections import Counter
from itertools import combinations
import hashlib
from ..poi_repository import POIRepository, TAG_GROUPS


class ZoneCoverageAnalyzer:
    def __init__(self, zone_id, repository=None):
        self.repository = repository or POIRepository()
        if zone_id not in self.repository.zone_order:
            raise ValueError(f"Unknown walk zone: {zone_id}")
        self.zone_id = zone_id

    def analyze(self):
        repo = self.repository
        pois = repo.get_pois_by_zone(self.zone_id)
        coverage, memberships = {}, {}
        for group in TAG_GROUPS:
            counts = Counter(t for p in pois for t in getattr(p, group))
            frequency = {t: counts[t] for t in repo.taxonomy[group]}
            coverage[group] = dict(frequency=frequency, zero_coverage=[t for t, n in frequency.items() if n == 0],
                                   low_coverage=[t for t, n in frequency.items() if n == 1])
            for tag in frequency:
                memberships[f"{group}.{tag}"] = {p.id for p in pois if tag in getattr(p, group)}
        correlated = []
        for (a, x), (b, y) in combinations(memberships.items(), 2):
            if len(x & y) >= 2 and len(x & y) / len(x | y) >= .8:
                correlated.append(dict(tags=[a, b], jaccard=len(x & y) / len(x | y), shared_poi_count=len(x & y)))
        museum = [p for p in pois if "museum_visit" in p.experience_tags]
        coordinates = [p.coordinates for p in pois if p.coordinates]
        rows = [p for p in repo._raw['pois'] if p['walk_zone']['id'] == self.zone_id]
        roles = Counter(p.get('route_role', {}).get('primary', 'unaudited') for p in rows)
        categories = Counter(p['category']['en'] for p in rows)
        return dict(walk_zone=self.zone_id, poi_count=len(pois), coverage=coverage,
                    route_role_coverage=dict(roles), category_distribution=dict(categories),
                    largest_category_fraction=max(categories.values(), default=0)/len(pois) if pois else 0,
                    strong_themes={g: sorted((t for t, n in c['frequency'].items() if n >= 2),
                        key=lambda t: (-c['frequency'][t], t)) for g, c in coverage.items()},
                    highly_correlated_tags=correlated,
                    definitions=dict(low_coverage="count = 1", highly_correlated="Jaccard >= 0.8, joint count >= 2; descriptive co-occurrence, not causal or Pearson correlation"),
                    production_sha256=hashlib.sha256(repo.path.read_bytes()).hexdigest(),
                    museum_dependency=dict(definition="museum_visit tag; does not imply indoor-only or required admission",
                        count=len(museum), fraction=len(museum)/len(pois) if pois else 0,
                        non_museum_count=len(pois)-len(museum),
                        museum_pois_supporting_walk_stop=sum("walk_stop" in p.visit_profile.supported_modes for p in museum)),
                    geography=dict(coordinate_system="GCJ-02", missing_count=len(pois)-len(coordinates),
                        bbox=[min(p[i] for p in coordinates) for i in (0, 1)] + [max(p[i] for p in coordinates) for i in (0, 1)] if coordinates else None,
                        pois=[dict(id=p.id, name=p.name_zh, coordinates=p.coordinates) for p in pois]))


class WestBundCoverageAnalyzer(ZoneCoverageAnalyzer):
    """Compatibility entry point for the accepted pilot and its existing CLI."""

    def __init__(self, repository=None):
        super().__init__('west_bund', repository)

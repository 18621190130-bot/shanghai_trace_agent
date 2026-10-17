"""Offline exact-name resolution. No external geocoding or inferred coordinates."""

import re
from dataclasses import dataclass, field

from .geo_utils import haversine_km


def normalize(text):
    return re.sub(r"[\s’'\-–—]+", " ", text.casefold()).strip()


@dataclass
class ResolvedLocation:
    coordinates: tuple[float, float] | None = None
    zone_id: str | None = None
    poi_id: str | None = None
    warnings: list[str] = field(default_factory=list)


class LocationResolver:
    def __init__(self, repository):
        self.repo = repository
        self.names = {}
        for item in repository.get_raw_data()["pois"]:
            for name in [item["name"]["zh"], item["name"]["en"], *item["name"].get("aliases", [])]:
                self.names.setdefault(normalize(name), set()).add(item["id"])
        self.zone_names = {}
        for zone in repository.get_raw_data()["metadata"]["walk_zones"]:
            for name in (zone["id"], zone["name_zh"], zone["name_en"]):
                self.zone_names[normalize(name)] = zone["id"]
        self.zone_names.update({normalize("West Bund"): "west_bund", normalize("Hongkou"): "hongkou_literary"})

    def resolve(self, text):
        key = normalize(text)
        ids = self.names.get(key, set())
        if len(ids) > 1:
            return ResolvedLocation(warnings=["ambiguous_location: choose a specific catalog place or coordinates"])
        if ids:
            p = self.repo.get_poi_by_id(next(iter(ids)))
            return ResolvedLocation(p.coordinates, p.zone_id, p.id,
                                    ["catalog_location_is_approximate_map_anchor"])
        zone = self.zone_names.get(key)
        if zone:
            points = [p for p in self.repo.get_pois_by_zone(zone) if p.coordinates is not None]
            if points:
                anchor = min(points, key=lambda p: (sum(haversine_km(p.coordinates, q.coordinates) for q in points), p.id))
                return ResolvedLocation(anchor.coordinates, zone, warnings=[
                    "zone_start_is_representative_anchor_not_actual_user_position"])
        return ResolvedLocation(warnings=["unresolved_external_location: no geocoding in Phase 2"])

    def select_pois(self, values):
        result = []
        for value in values:
            if isinstance(value, int) and not isinstance(value, bool):
                ids = [p.id for p in self.repo.get_all_pois() if p.display_order == value]
            elif isinstance(value, str):
                ids = list(self.names.get(normalize(value), []))
                if self.repo.get_poi_by_id(value) is not None:
                    ids = [value]
            else:
                ids = []
            if len(ids) != 1:
                raise ValueError(f"Unknown or ambiguous selected place: {value}")
            if ids[0] not in result:
                result.append(ids[0])
        return result

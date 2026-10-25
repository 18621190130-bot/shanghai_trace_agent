"""Bounded curated themes selected only after actual engine feasibility checks."""

import copy
import hashlib
import json
from pathlib import Path

from .geo_utils import haversine_km, to_gcj02
from .intent_adapter import intent_to_route_request
from .models import RequestValidationError
from .poi_repository import TAG_GROUPS


class SurpriseRoutePolicy:
    def __init__(self, repository, engine, themes_path=None):
        self.repo, self.engine = repository, engine
        path = themes_path or Path(__file__).resolve().parents[1] / "data" / "surprise_themes.json"
        self.themes = json.loads(Path(path).read_text(encoding="utf-8"))["themes"]
        if not self.themes or len({t["name"] for t in self.themes}) != len(self.themes):
            raise RequestValidationError("Surprise themes must have unique names")
        for theme in self.themes:
            if not theme["zones"] or any(z not in repository.zone_order for z in theme["zones"]):
                raise RequestValidationError("Unknown theme zone")
            for group in TAG_GROUPS:
                if any(t not in repository.taxonomy[group] for t in theme[group]):
                    raise RequestValidationError("Unknown surprise theme tag")

    def choose(self, intent):
        if (intent.start_lat is None or intent.start_lng is None) and not intent.preferred_zone:
            raise RequestValidationError("Surprise me requires a usable start")
        start = None if intent.start_lat is None else to_gcj02(intent.start_lat, intent.start_lng, intent.start_coordinate_system)
        candidates = []
        for zone in self.repo.zone_order:
            if intent.preferred_zone is not None and zone != intent.preferred_zone:
                continue
            points = [p for p in self.repo.get_pois_by_zone(zone) if p.coordinates is not None]
            if not points:
                continue
            approach = min(haversine_km(start, p.coordinates) * self.engine.factor for p in points) if start else 0
            minimum_stay = min(min(p.visit_profile.stay_for(mode, intent.travel_pace)
                                   for mode in p.visit_profile.supported_modes) for p in points)
            if approach * 1000 / self.engine.speed + minimum_stay + self.engine.buffer > intent.available_minutes:
                continue
            for theme in self.themes:
                if zone not in theme["zones"]:
                    continue
                curated = copy.deepcopy(intent)
                curated.preferred_zone = zone
                for group in TAG_GROUPS:
                    setattr(curated, group, list(theme[group]))
                plan = self.engine.generate_route(intent_to_route_request(curated))
                if plan.status != "success" or len(plan.ordered_pois) < (3 if start is None else 1) or any(n.walk_zone != zone for n in plan.ordered_pois):
                    continue
                # Nearest reachable area first, then richer checked routes; stable hash breaks ties.
                digest = hashlib.sha256(f"{intent.surprise_seed}:{zone}:{theme['name']}".encode()).hexdigest()
                rank = (approach, -len(plan.ordered_pois), digest) if start else (0, digest, -len(plan.ordered_pois))
                candidates.append((rank, curated, theme["name"], plan))
        if not candidates:
            return None
        _, curated, theme, plan = min(candidates, key=lambda item: item[0])
        return curated, theme, plan

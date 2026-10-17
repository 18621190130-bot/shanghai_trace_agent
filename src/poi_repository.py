"""Validate the actual v3 knowledge-base structure and index all POIs."""

import copy
import json
import math
from pathlib import Path

from .geo_utils import to_gcj02
from .models import DataValidationError, POI, VisitProfile, VisitTimes

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "pois.json"
TAG_GROUPS = ("interest_tags", "experience_tags", "culture_tags")


def numeric(value, label, minimum=0, maximum=None):
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise DataValidationError(f"{label}: expected a finite number")
    if value < minimum or (maximum is not None and value > maximum):
        raise DataValidationError(f"{label}: out of range")
    return float(value)


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{label}: expected a nonempty string")
    return value


class POIRepository:
    def __init__(self, path=DEFAULT_DATA_PATH, *, spatial_profiles=None):
        self.path = Path(path)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            self._load(raw)
            self._apply_spatial_profiles(spatial_profiles)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            if isinstance(exc, DataValidationError):
                raise
            raise DataValidationError(f"Invalid knowledge base {self.path}: {exc}") from exc

    def _apply_spatial_profiles(self, profiles):
        from dataclasses import replace
        from .spatial_profiles import SpatialProfileRepository, DEFAULT_SPATIAL_PATH, anchor
        self.spatial_profiles = None
        # Historical/candidate KBs remain independent of the current production sidecar.
        if profiles is None and self.path.resolve() == DEFAULT_DATA_PATH.resolve() and DEFAULT_SPATIAL_PATH.exists():
            profiles = SpatialProfileRepository(core_ids=self._pois)
        elif isinstance(profiles, dict):
            profiles = SpatialProfileRepository(records=profiles,core_ids=self._pois)
        if profiles is None:return
        if set(profiles.all()) != set(self._pois):raise DataValidationError('Spatial/Core identity sets differ')
        self.spatial_profiles = profiles
        for pid,poi in self._pois.items():
            profile = profiles.get(pid)
            if profile['spatial_type'] != 'POINT':
                target = anchor(profile['route_anchor'])
                self._pois[pid] = replace(poi,coordinates=(target.lat,target.lng))

    def get_spatial_profile(self, poi_id):
        return self.spatial_profiles.get(poi_id) if self.spatial_profiles is not None else None

    def _load(self, raw):
        if not isinstance(raw, dict):
            raise DataValidationError("Root must be an object")
        self._raw = copy.deepcopy(raw)
        metadata = raw["metadata"]
        self.taxonomy = copy.deepcopy(metadata["tag_taxonomy"])
        for group in TAG_GROUPS:
            if not isinstance(self.taxonomy[group], dict) or not self.taxonomy[group]:
                raise DataValidationError(f"metadata.tag_taxonomy.{group}: expected vocabulary object")
            for key, description in self.taxonomy[group].items():
                text(key, group)
                text(description, f"{group}.{key}")
        self.zone_order = []
        zone_declarations = metadata["walk_zones"]
        if not isinstance(zone_declarations, list) or not zone_declarations:
            raise DataValidationError("metadata.walk_zones: expected nonempty list")
        for zone in zone_declarations:
            zid = text(zone["id"], "walk zone id")
            text(zone["name_zh"], f"zone {zid} name_zh")
            if zid in self.zone_order:
                raise DataValidationError(f"Duplicate walk zone: {zid}")
            self.zone_order.append(zid)
        self.defaults = copy.deepcopy(raw["route_engine_defaults"])
        enabled = self.defaults.get('route_composition_enabled_zones', [])
        if not isinstance(enabled, list) or any(z not in self.zone_order for z in enabled):
            raise DataValidationError('invalid route_composition_enabled_zones')
        for key in ("walking_speed_m_per_min", "walking_distance_factor"):
            if numeric(self.defaults[key], key) <= 0:
                raise DataValidationError(f"{key}: must be positive")
        numeric(self.defaults["route_buffer_minutes"], "route_buffer_minutes")
        cap = self.defaults["max_pois_default"]
        if type(cap) is not int or cap <= 0:
            raise DataValidationError("max_pois_default: expected positive integer")
        if type(self.defaults["prefer_same_walk_zone"]) is not bool:
            raise DataValidationError("prefer_same_walk_zone: expected boolean")
        text(self.defaults["cross_zone_transfer_penalty"], "cross_zone_transfer_penalty")
        if self.defaults.get("default_walk_zone") not in self.zone_order:
            raise DataValidationError("default_walk_zone: unknown zone")
        targets = self.defaults.get("richness_targets")
        if not isinstance(targets, list) or not targets:
            raise DataValidationError("richness_targets: expected nonempty list")
        previous_max = 0
        for target in targets:
            for key in ("max_minutes", "min_stops", "max_stops"):
                if type(target[key]) is not int or target[key] <= 0:
                    raise DataValidationError(f"richness_targets.{key}: expected positive integer")
            if target["max_minutes"] <= previous_max or target["min_stops"] > target["max_stops"]:
                raise DataValidationError("richness_targets: invalid ranges")
            previous_max = target["max_minutes"]
        for key in ("interest_tag_match", "experience_tag_match", "culture_tag_match",
                    "same_zone_bonus", "distance_penalty_per_km"):
            numeric(self.defaults["scoring_weights"][key], f"scoring_weights.{key}")
        if not isinstance(raw["pois"], list):
            raise DataValidationError("pois: expected list")
        self._pois = {}
        for item in raw["pois"]:
            poi = self._parse_poi(item)
            if poi.id in self._pois:
                raise DataValidationError(f"Duplicate POI ID: {poi.id}")
            self._pois[poi.id] = poi
        orders = [p.display_order for p in self._pois.values()]
        if orders != list(range(1, len(orders) + 1)):
            raise DataValidationError("display_order must follow file order consecutively from 1")
        if type(metadata["poi_count"]) is not int or metadata["poi_count"] != len(self._pois):
            raise DataValidationError("metadata.poi_count disagrees with pois")
        if type(metadata["walk_zone_count"]) is not int or metadata["walk_zone_count"] != len(self.zone_order):
            raise DataValidationError("metadata.walk_zone_count disagrees with walk_zones")
        for zone in zone_declarations:
            if type(zone["poi_count"]) is not int or zone["poi_count"] != len(self.get_pois_by_zone(zone["id"])):
                raise DataValidationError(f"zone {zone['id']}: poi_count mismatch")
        for poi in self._pois.values():
            if poi.zone_id in enabled and poi.counts_as_route_stop and poi.route_role_primary is None:
                raise DataValidationError('enabled zone has a POI without explicit primary role')

    def _parse_poi(self, item):
        pid = text(item["id"], "POI id")
        from .route_composition import ROLES
        role = item.get('route_role')
        if role is not None and (not isinstance(role, dict) or role.get('primary') not in ROLES
                or not isinstance(role.get('eligible'), list) or role['primary'] not in role['eligible']
                or len(set(role['eligible'])) != len(role['eligible']) or any(r not in ROLES for r in role['eligible'])):
            raise DataValidationError(f'{pid}: invalid route_role')
        selectable = item.get('counts_as_route_stop', True)
        if type(selectable) is not bool or (item.get('route_selectable', True) is False and selectable):
            raise DataValidationError(f'{pid}: invalid route stop eligibility')
        order = item["display_order"]
        if type(order) is not int or order < 1:
            raise DataValidationError(f"{pid}.display_order: expected positive integer")
        poi_type = item["poi_type"]
        if poi_type not in ("landmark", "venue", "park", "street", "district"):
            raise DataValidationError(f"{pid}.poi_type: invalid type")
        name, location, zone, tags, planning = (item[k] for k in ("name", "location", "walk_zone", "tags", "planning"))
        zh, en = text(name["zh"], f"{pid}.name.zh"), text(name["en"], f"{pid}.name.en")
        zid = text(zone["id"], f"{pid}.walk_zone.id")
        if zid not in self.zone_order:
            raise DataValidationError(f"{pid}: unknown walk zone {zid}")
        zone_zh = text(zone["name_zh"], f"{pid}.walk_zone.name_zh")
        zone_en = text(zone["name_en"], f"{pid}.walk_zone.name_en")
        for group in TAG_GROUPS:
            if not isinstance(tags[group], list) or any(not isinstance(t, str) or t not in self.taxonomy[group] for t in tags[group]):
                raise DataValidationError(f"{pid}.{group}: invalid tag list")
        area = poi_type in ("street", "district")
        lat, lng = (location["representative_lat"], location["representative_lng"]) if area else (location["lat"], location["lng"])
        if lat is not None:
            numeric(lat, f"{pid}.lat", -90, 90)
        if lng is not None:
            numeric(lng, f"{pid}.lng", -180, 180)
        system = text(location["coordinate_system"], f"{pid}.coordinate_system")
        coordinates = to_gcj02(lat, lng, system) if lat is not None and lng is not None else None
        if "recommended_stay" in planning or "recommended_stay" in item:
            raise DataValidationError(f"{pid}: legacy recommended_stay is not allowed")
        profile = item["visit_profile"]
        default = profile["default_mode"]
        supported = profile["supported_modes"]
        if not isinstance(supported, list) or not supported or any(m not in ("walk_stop", "full_visit") for m in supported):
            raise DataValidationError(f"{pid}: invalid supported visit modes")
        if len(set(supported)) != len(supported) or default not in supported:
            raise DataValidationError(f"{pid}: default mode must be supported and modes unique")
        modes = profile["modes"]
        if not isinstance(modes, dict) or set(modes) != set(supported):
            raise DataValidationError(f"{pid}: modes must exactly match supported_modes")
        times = {}
        details = item["visit_mode_details"]
        if not isinstance(details, dict) or set(details) != set(supported):
            raise DataValidationError(f"{pid}: visit_mode_details must match supported_modes")
        for mode in supported:
            if not isinstance(modes[mode], dict) or set(modes[mode]) != {"quick", "standard", "deep"}:
                raise DataValidationError(f"{pid}.{mode}: expected quick/standard/deep")
            values = [numeric(modes[mode][pace], f"{pid}.{mode}.{pace}") for pace in ("quick", "standard", "deep")]
            if values[0] <= 0 or values != sorted(values):
                raise DataValidationError(f"{pid}.{mode}: require 0 < quick <= standard <= deep")
            times[mode] = VisitTimes(*values)
            if details[mode]["environment"] not in ("indoor", "outdoor", "mixed"):
                raise DataValidationError(f"{pid}.{mode}: invalid environment")
            if details[mode]["ticket_required"] is not None and type(details[mode]["ticket_required"]) is not bool:
                raise DataValidationError(f"{pid}.{mode}: ticket_required must be boolean or null")
            text(details[mode]["scope"], f"{pid}.{mode}.scope")
        pending = item.get("visit_profile_calibration", {}).get("pending_manual_calibration_modes", [])
        if not isinstance(pending, list) or any(m not in supported for m in pending):
            raise DataValidationError(f"{pid}: invalid pending calibration modes")
        environment = planning["environment"]
        if environment not in ("indoor", "outdoor", "mixed"):
            raise DataValidationError(f"{pid}: invalid environment")
        crowd = planning["crowd_level_default"]
        if crowd not in (None, "low", "medium", "high"):
            raise DataValidationError(f"{pid}: invalid crowd level")
        hours = planning["opening_hours"]
        if hours is not None and not isinstance(hours, str):
            raise DataValidationError(f"{pid}: opening_hours must be text or null")
        for flag in ("ticket_required", "reservation_required"):
            if planning[flag] is not None and type(planning[flag]) is not bool:
                raise DataValidationError(f"{pid}.{flag}: expected boolean or null")
        return POI(id=pid, display_order=order, poi_type=poi_type, name_zh=zh, name_en=en,
                   zone_id=zid, zone_name_en=zone_en, zone_name_zh=zone_zh,
                   **{g: tuple(sorted(set(tags[g]))) for g in TAG_GROUPS},
                   coordinates=coordinates, original_coordinates=(lat, lng), original_coordinate_system=system,
                   visit_profile=VisitProfile(default, tuple(supported), times), visit_mode_details=copy.deepcopy(details),
                   pending_calibration_modes=tuple(pending), coordinate_note=location.get("coordinate_note"),
                   environment=environment, crowd_level=crowd, opening_hours=hours,
                   ticket_required=planning["ticket_required"], reservation_required=planning["reservation_required"],
                   route_role_primary=role['primary'] if role else None,
                   route_role_eligible=tuple(role['eligible']) if role else (), counts_as_route_stop=selectable)

    def get_all_pois(self):
        return sorted(self._pois.values(), key=lambda p: p.display_order)

    def get_poi_by_id(self, poi_id):
        return self._pois.get(poi_id)

    def get_pois_by_zone(self, zone_id):
        return [p for p in self.get_all_pois() if p.zone_id == zone_id]

    def _by_tag(self, group, tag):
        if tag not in self.taxonomy[group]:
            raise ValueError(f"Unknown {group}: {tag}")
        return [p for p in self.get_all_pois() if tag in getattr(p, group)]

    def get_pois_by_interest_tag(self, tag):
        return self._by_tag("interest_tags", tag)

    def get_pois_by_experience_tag(self, tag):
        return self._by_tag("experience_tags", tag)

    def get_pois_by_culture_tag(self, tag):
        return self._by_tag("culture_tags", tag)

    def get_missing_coordinate_ids(self):
        return [p.id for p in self.get_all_pois() if p.coordinates is None]

    def get_raw_data(self):
        return copy.deepcopy(self._raw)

"""Reproducible Phase 1.5B migration from the untouched original v3 dataset.

Run from any directory. Writes only data/pois.json. Additional mode estimates
were explicitly authorized by the user and are marked pending calibration.
"""

import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZONES = {
    "wukang_fuxing_xujiahui": ("武康—复兴—徐家汇", "Wukang–Fuxing–Xujiahui"),
    "old_city_central": ("老城厢—新天地—外滩", "Old City–Xintiandi–Bund"),
    "hongkou_literary": ("鲁迅公园—四川北路", "Lu Xun Park–North Sichuan Road"),
    "west_bund": ("徐汇西岸滨江", "West Bund Waterfront"),
}

# Tuple values are quick / standard / deep, in minutes.
# Non-default alternatives marked below are product estimates, not reviewed facts.
PROFILES = {
    "p2": ("walk_stop", {"walk_stop": (10, 20, 35)}),
    "p4": ("full_visit", {"full_visit": (15, 30, 45)}),
    "p5": ("full_visit", {"full_visit": (30, 75, 120), "walk_stop": (15, 25, 40)}),
    "p7": ("walk_stop", {"walk_stop": (15, 30, 60), "full_visit": (30, 60, 90)}),
    "p9": ("walk_stop", {"walk_stop": (20, 40, 60)}),
    "p10": ("walk_stop", {"walk_stop": (15, 30, 60), "full_visit": (30, 60, 90)}),
    "p11": ("walk_stop", {"walk_stop": (10, 15, 25)}),
    "p12": ("walk_stop", {"walk_stop": (5, 10, 20)}),
    "p13": ("walk_stop", {"walk_stop": (5, 15, 25)}),
    "p14": ("walk_stop", {"walk_stop": (10, 25, 45)}),
    "p15": ("walk_stop", {"walk_stop": (30, 45, 60), "full_visit": (60, 90, 120)}),
    "p16": ("full_visit", {"full_visit": (30, 50, 75)}),
    "p20": ("full_visit", {"full_visit": (20, 40, 60)}),
    "p21": ("full_visit", {"full_visit": (25, 45, 70)}),
    "p23": ("walk_stop", {"walk_stop": (15, 30, 50), "full_visit": (30, 60, 90)}),
    "p24": ("full_visit", {"full_visit": (30, 60, 90), "walk_stop": (15, 25, 40)}),
    "p25": ("walk_stop", {"walk_stop": (10, 25, 40), "full_visit": (20, 40, 60)}),
    "p26": ("full_visit", {"full_visit": (15, 30, 45)}),
    "p27": ("walk_stop", {"walk_stop": (15, 35, 60), "full_visit": (30, 60, 90)}),
    "p28": ("full_visit", {"full_visit": (30, 75, 120), "walk_stop": (10, 20, 30)}),
    "p29": ("walk_stop", {"walk_stop": (15, 25, 35), "full_visit": (45, 75, 120)}),
    "p30": ("walk_stop", {"walk_stop": (15, 30, 60), "full_visit": (30, 60, 90)}),
    "p31": ("full_visit", {"full_visit": (30, 60, 100), "walk_stop": (10, 20, 30)}),
    "p32": ("walk_stop", {"walk_stop": (10, 20, 30), "full_visit": (20, 35, 50)}),
    "p33": ("full_visit", {"full_visit": (15, 30, 40)}),
    "p34": ("full_visit", {"full_visit": (30, 60, 90)}),
    "p35": ("walk_stop", {"walk_stop": (20, 30, 45), "full_visit": (60, 90, 150)}),
}
ESTIMATED_ALTERNATIVES = {"p5": "walk_stop", "p7": "full_visit", "p10": "full_visit",
                          "p23": "full_visit", "p24": "walk_stop", "p25": "full_visit",
                          "p27": "full_visit", "p28": "walk_stop", "p30": "full_visit", "p31": "walk_stop"}
TYPES = {"p2": "street", "p4": "venue", "p5": "venue", "p7": "district", "p9": "district",
         "p10": "district", "p11": "district", "p12": "district", "p13": "landmark", "p14": "landmark",
         "p15": "district", "p16": "park", "p20": "venue", "p21": "venue", "p23": "district",
         "p24": "venue", "p25": "venue", "p26": "venue", "p27": "venue", "p28": "venue",
         "p29": "venue", "p30": "district", "p31": "venue", "p32": "landmark", "p33": "venue",
         "p34": "street", "p35": "district"}

# Static coordinate enrichment only. No map/network calls during migration or routing.
COORDINATE_FILLS = {
    "p20": (31.225879, 121.492466, "GCJ-02/Amap POI anchor",
            "https://ditu.amap.com/place/B00155FHOA",
            "Published temple POI anchor matching Fangbang Middle Road 249; visitor entrance not verified."),
    "p23": (31.214509, 121.468956, "GCJ-02/Amap representative anchor",
            "https://ditu.amap.com/place/B001574I9I",
            "Published Sinan Mansions complex anchor (source address 509, existing catalog address 523 Fuxing Middle Road). Representative district point, not a verified gate or centroid."),
    "p24": (31.22206, 121.47069, "WGS84/OpenStreetMap approximation",
            "https://mapcarta.com/W372180467",
            "Historic First Congress site anchor (OSM way 372180467), not the new exhibition building entrance. Replaces the incomplete legacy pair as a whole; manual entrance/scope review remains needed."),
    "p26": (31.265534037082084, 121.4765340501877, "WGS84 planning approximation",
            "https://hkda.shhk.gov.cn/hkda/lswm/hk_protalSite/",
            "Hongkou Archives public map record WM00377 matches Duolun Road Lane 201 No. 2. Map uses Tianditu; precise feature datum is unverified, provisionally treated as WGS84. Needs manual coordinate review; not a verified entrance."),
}


def enrich_coordinates(poi):
    pid, location = poi["id"], poi["location"]
    if pid not in COORDINATE_FILLS and pid != "p31":
        return
    location["coordinate_previous_record"] = {
        key: location.get(key) for key in ("lat", "lng", "coordinate_system")}
    if pid == "p31":
        # West Bund's official BMap destination is BD-09 (lat, lng).
        source_lat, source_lng = 31.193849, 121.476902
        x, y = source_lng - 0.0065, source_lat - 0.006
        x_pi = math.pi * 3000 / 180
        z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y*x_pi)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x*x_pi)
        lat, lng = round(z * math.sin(theta), 6), round(z * math.cos(theta), 6)
        system = "GCJ-02/approximate conversion from official BD09 map anchor"
        source = "https://www.westbund.com/en/index/KEY-PROJECTS/detail_6f9E8.html"
        note = "Official West Bund Start Museum BMap destination at 111 Ruining Road; static approximate BD09-to-GCJ02 conversion. Not a verified visitor entrance."
        location["coordinate_source_original"] = {"lat": source_lat, "lng": source_lng, "coordinate_system": "BD09"}
    else:
        lat, lng, system, source, note = COORDINATE_FILLS[pid]
    location.update(lat=lat, lng=lng, coordinate_system=system,
                    coordinate_source=source, coordinate_note=note,
                    coordinate_checked_on="2026-10-03", coordinate_status="map_anchor_not_verified_entrance")
    if pid == "p26":
        location["coordinate_source_record"] = "WM00377 in assets/index-AH2zv9w_.js"


def new_poi(pid, zh, en, address, zone, category, tags, summary, bridge, location):
    return {
        "id": pid, "name": {"zh": zh, "en": en, "aliases": []},
        "location": {"address_zh": address, **location},
        "walk_zone": {"id": zone}, "category": {"zh": category[0], "en": category[1]},
        "tags": dict(zip(("interest_tags", "experience_tags", "culture_tags"), tags)),
        "planning": {"environment": "mixed", "crowd_level_default": None,
                     "ticket_required": None, "reservation_required": None,
                     "opening_hours": None, "opening_hours_source": None, "last_verified": None},
        "content": {"summary_zh": summary},
        "culture_bridge": {"explanation_en": bridge,
                           "content_status": "product wording based on user-confirmed Phase 1.5B scope; not externally fact-checked"},
        "verification": {"status": "user_confirmed_scope_with_approximate_map_anchor",
                         "source": "Phase 1.5B final calibration V2", "checked_on": "2026-10-03",
                         "note": "Live access, precise entrances and representative anchors still require manual verification."},
    }


def build():
    raw = json.loads((ROOT / "data" / "archive" / "shanghaitrace_poi_kb_v3_minimal_tags.json").read_text(encoding="utf-8"))
    raw["pois"] = [p for p in raw["pois"] if p["id"] not in ("p1", "p22")]
    raw["pois"].extend([
        new_poi("p32", "徐家汇天主堂", "St. Ignatius Cathedral / Xujiahui Cathedral", "上海市徐汇区蒲西路158号",
                "wukang_fuxing_xujiahui", ("历史宗教建筑", "Historic Religious Architecture"),
                (["architecture", "history", "religion"], ["iconic_landmark", "architecture_detail", "photogenic"],
                 ["sino_foreign_exchange", "modern_shanghai", "religious_culture"]),
                "以建筑外观观察为默认体验，可在允许入内时进一步参访教堂。",
                "Use the cathedral to introduce Catholic history in Shanghai, Western religious architecture, and Xujiahui's role in Sino-Western cultural exchange.",
                {"lat": 31.19337, "lng": 121.43258, "coordinate_system": "WGS84/OpenStreetMap approximation",
                 "coordinate_source": "https://mapcarta.com/N11224212192", "coordinate_source_feature": "OpenStreetMap node 11224212192",
                 "coordinate_note": "Approximate map anchor; not a verified visitor entrance."}),
        new_poi("p33", "徐家汇书院", "Zikawei Library / Xujiahui Academy", "上海市徐汇区漕溪北路158号",
                "wukang_fuxing_xujiahui", ("当代公共文化空间", "Contemporary Public Cultural Space"),
                (["architecture", "local_life", "history"], ["architecture_detail", "quiet_walk"],
                 ["modern_shanghai", "public_life", "sino_foreign_exchange"]),
                "以短时入内参访和公共阅读空间观察为核心体验。",
                "Connect contemporary public reading culture with the Xujiahui cultural district and the relationship between historic Shanghai and modern public cultural spaces.",
                {"lat": 31.1925, "lng": 121.43252, "coordinate_system": "WGS84/OpenStreetMap approximation",
                 "coordinate_source": "https://mapcarta.com/N10610507005", "coordinate_source_feature": "OpenStreetMap node 10610507005",
                 "coordinate_note": "Contemporary academy anchor, not the separate historic Bibliotheca Zi-Ka-Wei; entrance not verified."}),
        new_poi("p34", "南京路步行街", "Nanjing Road Pedestrian Street", "南京东路步行街核心路段：西藏中路—中山东一路",
                "old_city_central", ("商业步行街", "Commercial Pedestrian Street"),
                (["shopping_lifestyle", "history", "architecture", "modern_city"],
                 ["iconic_landmark", "street_scene", "shopping_leisure", "photogenic"],
                 ["modern_shanghai", "public_life", "sino_foreign_exchange"]),
                "将南京东路核心步行路段作为完整游览目的地，而非单一建筑或短暂停留点。",
                "Explore Shanghai's modern commercial history, department-store culture, urban consumer culture, and the contrast between historic commercial Shanghai and today's global shopping street.",
                {"representative_lat": 31.2359, "representative_lng": 121.4805,
                 "coordinate_system": "WGS84 planning approximation",
                 "coordinate_source": "https://opentravelguide.com/china/shanghai/shanghai/attractions/nanjing-road-pedestrian-street/",
                 "coordinate_note": "Provisional product anchor based on a published location; source datum unverified, provisionally interpreted as WGS84. Not a verified midpoint or street entrance. Needs manual coordinate review."}),
        new_poi("p35", "徐家汇商圈", "Xujiahui Commercial District", "美罗城、港汇恒隆广场及徐家汇核心商业公共空间",
                "wukang_fuxing_xujiahui", ("商业区域", "Commercial District"),
                (["shopping_lifestyle", "modern_city", "architecture"], ["shopping_leisure", "street_scene", "local_atmosphere"],
                 ["modern_shanghai", "public_life"]),
                "包含美罗城、港汇恒隆广场及其之间的核心公共空间；不是某一栋商场。",
                "Discuss contemporary urban commercial life, shopping malls as public urban spaces, and Xujiahui's evolution into a major commercial center.",
                {"representative_lat": 31.1954, "representative_lng": 121.4338,
                 "coordinate_system": "WGS84 planning approximation",
                 "coordinate_source": "https://mapcarta.com/W225521733",
                 "coordinate_note": "Product-selected approximate public-space anchor northwest of the published Metro City anchor (31.1949, 121.4352), toward Grand Gateway. Not an entire-district centroid or verified entrance. Needs manual coordinate review."}),
    ])
    for order, poi in enumerate(raw["pois"], 1):
        pid = poi["id"]
        enrich_coordinates(poi)
        poi["display_order"] = order
        poi["poi_type"] = TYPES[pid]
        zid = poi["walk_zone"]["id"]
        if zid == "hengfu":
            zid = "wukang_fuxing_xujiahui"
        poi["walk_zone"] = {"id": zid, "name_zh": ZONES[zid][0], "name_en": ZONES[zid][1]}
        default, modes = PROFILES[pid]
        poi["planning"].pop("recommended_stay", None)
        poi["visit_profile"] = {"default_mode": default, "supported_modes": list(modes),
                                "modes": {mode: dict(zip(("quick", "standard", "deep"), times)) for mode, times in modes.items()}}
        poi["visit_profile_calibration"] = {
            "time_basis": "product_planning_estimate", "default_source": "Phase 1.5A proposal, adopted by final Phase 1.5B where not overridden",
            "pending_manual_calibration_modes": [ESTIMATED_ALTERNATIVES[pid]] if pid in ESTIMATED_ALTERNATIVES else [],
        }
        if pid in ("p4", "p9", "p15", "p16", "p20", "p29", "p32", "p33", "p34", "p35"):
            poi["visit_profile_calibration"]["default_source"] = "User-confirmed Phase 1.5B final calibration V2"
        if pid == "p33":
            poi["visit_profile_calibration"]["time_basis"] = "user_confirmed_personal_visit_estimate_not_population_average"
        details = {}
        for mode in modes:
            requires_ticket = poi["planning"]["ticket_required"] if mode == "full_visit" else False
            environment = poi["planning"]["environment"]
            scope = "Key exterior/public-space observation." if mode == "walk_stop" else "Visit this destination in depth; full_visit does not imply indoor or ticketed access."
            if mode == "walk_stop" and poi["poi_type"] in ("landmark", "venue"):
                environment = "outdoor"
            if pid == "p15":
                requires_ticket = mode == "full_visit"
                environment = "mixed" if mode == "full_visit" else "outdoor"
                scope = ("Ticketed Yu Garden garden visit plus surrounding shopping area and streets." if mode == "full_visit"
                         else "Yu Garden shopping area and surrounding streets; excludes ticketed garden entry.")
            if pid == "p29":
                scope = "Exterior tanks, industrial heritage and waterfront public space; no exhibition entry." if mode == "walk_stop" else "Enter the exhibition venue to view art."
            if pid == "p35":
                requires_ticket = False
                scope = "Brief district observation, short mall stops and supplies." if mode == "walk_stop" else "Shopping, dining and exploration of Metro City, Grand Gateway and surrounding public spaces."
            if pid in ("p33", "p34"):
                requires_ticket = None if pid == "p33" else False
            if pid in ("p16", "p34"):
                environment = "outdoor"
            details[mode] = {"environment": environment, "ticket_required": requires_ticket, "scope": scope}
        poi["visit_mode_details"] = details
        if pid == "p15":
            poi["content"]["summary_zh"] = "默认游览豫园商城及周边街区；full_visit 模式增加购票入园并保留周边游览。"
            poi["culture_bridge"]["explanation_en"] = "Distinguish the surrounding shopping streets from the ticketed garden, then connect garden culture with Shanghai's historical commercial core."
        if poi["poi_type"] in ("street", "district") and "representative_lat" not in poi["location"]:
            poi["location"]["representative_lat"] = poi["location"].pop("lat", None)
            poi["location"]["representative_lng"] = poi["location"].pop("lng", None)
            if pid not in COORDINATE_FILLS:
                poi["location"]["coordinate_note"] = "Legacy point reused as representative anchor; not the whole area's unique location or verified entry/exit."
    metadata = raw["metadata"]
    metadata.update(version="poi-kb-v4-phase1.5b-final-calibration-v2", poi_count=27, walk_zone_count=4)
    metadata["walk_zones"] = [{"id": zid, "name_zh": names[0], "name_en": names[1],
                               "poi_count": sum(p["walk_zone"]["id"] == zid for p in raw["pois"])} for zid, names in ZONES.items()]
    metadata["design_notes"] = ["Phase 1.5B: only walk_stop/full_visit; full_visit describes a main destination, not indoor access.",
                                "Visit times are product estimates, with confirmed overrides and pending alternatives recorded per POI.",
                                "Stable internal IDs are preserved; display_order follows this data file from 1 to 27.",
                                "Street/district coordinates represent approximate anchors, not complete area footprints or access gates.",
                                "Dynamic access information is unknown unless explicitly provided to the route request."]
    raw["route_engine_defaults"]["default_walk_zone"] = "wukang_fuxing_xujiahui"
    raw["route_engine_defaults"]["richness_targets"] = [
        {"max_minutes": 90, "min_stops": 2, "max_stops": 3},
        {"max_minutes": 150, "min_stops": 3, "max_stops": 4},
        {"max_minutes": 240, "min_stops": 4, "max_stops": 5},
    ]
    return raw


if __name__ == "__main__":
    destination = ROOT / "data" / "pois.json"
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Calibrated 27 POIs; original v3 is unchanged.")

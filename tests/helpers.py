import copy
import json
import tempfile
from pathlib import Path
from src import POIRepository

# Historical Phase 1/2 assertions deliberately retain their validated 27-node
# fixture. Production/default selection is tested independently after promotion.
PRE_PHASE2_5_PATH = Path(__file__).resolve().parents[1] / 'data/archive/pois_pre_phase2_5.json'

def baseline_repository():
    return POIRepository(PRE_PHASE2_5_PATH)


def write_repository(test_case, raw):
    folder = tempfile.TemporaryDirectory()
    test_case.addCleanup(folder.cleanup)
    path = Path(folder.name) / "pois.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return POIRepository(path)


def subset(raw, pois):
    raw = copy.deepcopy(raw)
    raw["pois"] = copy.deepcopy(pois)
    for order, poi in enumerate(raw["pois"], 1):
        poi["display_order"] = order
    raw["metadata"]["poi_count"] = len(pois)
    for z in raw["metadata"]["walk_zones"]:
        z["poi_count"] = sum(p["walk_zone"]["id"] == z["id"] for p in pois)
    return raw

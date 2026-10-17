"""Offline calibrated routes: human output uses names/display order, not internal IDs."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import argparse
import json
import re
import sys
from pathlib import Path

from src import POIRepository, RouteEngine, RouteRequest
from src.models import DataValidationError

EXAMPLES = {
    "Route 1 — Architecture & Neighborhood Walk": RouteRequest(180, interest_tags=["architecture", "local_life"], experience_tags=["neighborhood_walk"], preferred_zone="wukang_fuxing_xujiahui"),
    "Route 2 — Literary Walk": RouteRequest(120, interest_tags=["literature"], experience_tags=["quiet_walk"], preferred_zone="hongkou_literary"),
    "Route 3 — West Bund Art Walk": RouteRequest(180, interest_tags=["art", "industrial_heritage"], experience_tags=["riverside_walk"], preferred_zone="west_bund"),
    "Route 4 — Nanjing Road Shopping Walk": RouteRequest(180, interest_tags=["shopping_lifestyle", "modern_city"], preferred_zone="old_city_central"),
    "Route 5 — Xujiahui Commercial Walk": RouteRequest(180, interest_tags=["shopping_lifestyle", "modern_city"], preferred_zone="wukang_fuxing_xujiahui"),
}


def user_text(value, repository):
    """Internal identities remain in machine JSON; user diagnostics use POI names."""
    def replacement(match):
        poi = repository.get_poi_by_id(match.group())
        return f"{poi.name_en} (#{poi.display_order})" if poi else "unknown location"
    value = re.sub(r"\bp\d+\b", replacement, str(value))
    for zone in repository.get_raw_data()["metadata"]["walk_zones"]:
        value = value.replace(zone["id"], zone["name_en"])
    return value


def render_plan(name, plan, repository):
    lines = [name, f"Status: {plan.status}"]
    if plan.selected_zone:
        lines.append("Zone: " + user_text(plan.selected_zone, repository))
    for index, node in enumerate(plan.ordered_pois, 1):
        lines.extend([
            f"  {index}. #{node.display_order} {node.name_zh} / {node.name_en}",
            f"     {node.selected_visit_mode} / {node.travel_pace}: estimated stay {node.estimated_stay_minutes:g} min",
            f"     Estimated previous leg: {node.estimated_distance_from_previous_stop_km:.3f} km / {node.estimated_walking_minutes:.2f} min",
            f"     Score: {node.recommendation_score:.3f}; matched tags: " + "; ".join(f"{g}={','.join(v)}" for g, v in node.matched_tags.items()),
            f"     Selection Reason: {node.selection_reason}",
            "     " + user_text(node.reason_for_recommendation, repository),
            "     Scope: " + str(node.visit_scope),
        ])
    if plan.total_estimated_minutes is not None:
        target = plan.richness_target
        lines.extend([
            "Preferred Richness: " + ("not configured" if target is None else f"{target['min_stops']}–{target['max_stops']} stops"),
            f"Actual Stops: {len(plan.ordered_pois)}",
            f"Preferred Richness Met: {plan.richness_target_met}",
        ])
        lines.extend([
            f"Estimated total: {plan.total_estimated_minutes:.2f} / {plan.request['available_minutes']} min; remaining {plan.remaining_minutes:.2f} min",
            f"Estimated distance: {plan.total_estimated_distance_km:.3f} km; walking {plan.total_estimated_walking_minutes:.2f} min; stays {plan.total_stay_minutes:g} min; buffer {plan.buffer_minutes:g} min",
            f"Cross-zone required: {plan.cross_zone_required}; richness target: {plan.richness_target}; met: {plan.richness_target_met}",
        ])
    lines.extend(["Budget scope: " + plan.time_budget_scope, "Explanation: " + user_text(plan.explanation, repository)])
    lines.extend("Error: " + user_text(e, repository) for e in plan.errors)
    lines.extend("Suggestion: " + user_text(s, repository) for s in plan.relaxation_suggestions)
    lines.extend("Warning: " + user_text(w, repository) for w in plan.warnings)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, help="Structured RouteRequest JSON; no natural language")
    parser.add_argument("--data", type=Path, help="Override knowledge-base path")
    parser.add_argument("--output", type=Path, help="Save complete machine JSON with stable internal identities")
    parser.add_argument("--json", action="store_true", help="Machine/debug output; default user output uses display_order and names")
    args = parser.parse_args()
    try:
        repository = POIRepository(args.data) if args.data else POIRepository()
        engine = RouteEngine(repository)
        if args.request:
            request = json.loads(args.request.read_text(encoding="utf-8-sig"))
            result = engine.generate_route(request)
            payload = result.to_dict()
            human = render_plan("Custom City Walk", result, repository)
            code = 0 if result.status == "success" else 2
        else:
            plans = {name: engine.generate_route(req) for name, req in EXAMPLES.items()}
            payload = {"examples": {name: p.to_dict() for name, p in plans.items()},
                       "missing_coordinate_poi_ids": repository.get_missing_coordinate_ids()}
            human = "\n\n".join(render_plan(name, p, repository) for name, p in plans.items())
            human += "\n\nMissing coordinate locations: " + ", ".join(user_text(pid, repository) for pid in repository.get_missing_coordinate_ids())
            code = 0 if all(p.status == "success" for p in plans.values()) else 2
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(rendered if args.json else human)
        return code
    except (DataValidationError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "validation_error", "errors": [str(exc)]}, ensure_ascii=True), file=sys.stderr)
        else:
            message = str(exc)
            if "repository" in locals():
                message = user_text(message, repository)
            print("Validation error: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

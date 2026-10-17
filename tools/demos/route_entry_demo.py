"""Interactive offline three-entry CLI. tools/demos/chat_demo.py explicitly enables the provider."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import argparse
import json
import sys
from dataclasses import asdict

from tools.demos.demo import render_plan, user_text
from src import POIRepository
from src.intent_models import RouteIntent, RouteMode, FeasibilityAction
from src.llm_client import MockLLMClient, DeepSeekLLMClient, LLMClientError
from src.mock_examples import PLAN_EXAMPLES
from src.models import RequestValidationError, DataValidationError
from src.route_entry import RouteEntryService
from src.kb_selection import KB_NAMES, resolve_poi_repository, kb_summary, render_kb_summary


def show_catalog(repo):
    for zone in repo.get_raw_data()["metadata"]["walk_zones"]:
        print("\n" + zone["name_en"] + " / " + zone["name_zh"])
        for p in repo.get_pois_by_zone(zone["id"]):
            print(f"  #{p.display_order} {p.name_en} / {p.name_zh}")
    print("\nChoose across any areas. Separate names or display numbers with semicolons.")


def selections(text):
    return [int(v.strip().lstrip('#')) if v.strip().lstrip('#').isdigit() else v.strip()
            for v in text.split(';') if v.strip()]


def read_clarifications(service, intent):
    for _ in range(8):
        intent = service.clarification.prepare(intent)
        if not intent.needs_clarification:
            return intent
        for question in intent.clarification_requests:
            if not intent.needs_clarification:
                return intent
            print("\n" + question.question)
            for index, option in enumerate(question.options, 1):
                print(f"  {index}. {option.label}")
            text = input("> ").strip()
            try:
                intent = service.answer_clarification(intent, question.field, text)
                print(render_intent(intent, service.repo, title="Merged Intent"))
            except (RequestValidationError, LLMClientError) as exc:
                print("Could not apply answer: " + str(exc) + "; previous intent preserved.")
                break
    raise RequestValidationError("Clarification limit reached; provide usable structured inputs")


def render_intent(intent, repo, title="Parsed Intent"):
    def show(value):
        if value is None or value == [] or value == "":
            return "-"
        return ", ".join(value) if isinstance(value, list) else str(value)
    def names(ids):
        return [repo.get_poi_by_id(pid).name_en for pid in ids]
    start = intent.start_location_text or (None if intent.start_lat is None else f"{intent.start_lat}, {intent.start_lng} ({intent.start_coordinate_system})")
    return "\n".join([title, "Mode: " + show(intent.route_mode),
        "Time: " + ("-" if intent.available_minutes is None else f"{intent.available_minutes} min"),
        "Start: " + show(start), "Interest: " + show(intent.interest_tags),
        "Experience: " + show(intent.experience_tags), "Culture: " + show(intent.culture_tags),
        "Avoid: " + show(intent.avoid_tags), "Avoid Places: " + show(names(intent.avoid_poi_ids)),
        "Unresolved Avoid: " + show(intent.unresolved_negative_preferences),
        "Must-go: " + show(names(intent.must_go_poi_ids)), "Pace: " + show(intent.travel_pace),
        "Preferred Zone: " + ("-" if intent.preferred_zone is None else user_text(intent.preferred_zone, repo)),
        "Max Walking Distance: " + ("-" if intent.max_walking_km is None else f"{intent.max_walking_km:g} km"),
        "Needs Clarification: " + str(intent.needs_clarification)])


def render_result(result, repo):
    intent = result.intent
    lines = [render_intent(intent, repo), "Status: " + result.status]
    if intent.semantic_concepts:
        lines.append('Semantic Expanded Tags:')
        for concept in intent.semantic_concepts:
            lines.append(f"  {concept['concept']}: Primary: {concept['primary']}; Secondary: {', '.join(concept['secondary']) or '-'}")
    if result.route_quality:
        quality = result.route_quality
        lines.extend([f"Route Quality Check: {quality.status}",
                      f"Minimum Viable City Walk: {quality.minimum_viable}",
                      f"Minimum Required Stops: {quality.minimum_required_stops}",
                      f"Actual Stops: {quality.actual_stops}",
                      ("Initial Quality Reason: " if quality.clarification_applied else "Reason: ")
                      + (", ".join(quality.reasons) or "no_anomaly_detected"),
                      f"Route Quality Clarification Applied: {quality.clarification_applied}"])
        if quality.preference_broadening:
            lines.append(f"Preference Broadening: {quality.preference_broadening}")
    if result.surprise_theme:
        lines.append("Surprise Theme: " + result.surprise_theme)
    if result.feasibility:
        check = result.feasibility
        estimate = "unknown" if check.estimated_minimum_minutes is None else f"{check.estimated_minimum_minutes:.2f}"
        lines.extend([f"Selected places minimum estimate: {estimate} min",
                      f"Walking-only feasible: {check.walking_only_feasible}",
                      "Selected places preserved: " + ", ".join(repo.get_poi_by_id(pid).name_en for pid in check.required_poi_ids)])
    for warning in result.warnings:
        lines.append("Warning: " + user_text(warning, repo))
    for question in intent.clarification_requests:
        lines.append("Clarification: " + question.question)
        lines.extend(f"  {o.label}" for o in question.options)
    if result.route_plan:
        title = ("Provisional Route" if result.status == 'needs_route_quality_clarification' else
                 "Suggested Places — not a complete City Walk" if result.status == 'insufficient_route' else "Generated Route")
        lines.append(render_plan(title, result.route_plan, repo))
        plan = result.route_plan
        if plan.composition_diagnostics:
            composition = plan.composition_diagnostics
            lines.extend([f"Route Composition Enabled: {composition['enabled']}",
                          f"Route Composition Passed: {composition['route_composition_passed']}",
                          f"Minimum Stop Count Passed: {composition['minimum_stop_count_passed']}",
                          f"Route Primary Roles: {composition['primary_role_counts']}"])
        lines.append("Time Utilization: " + ("-" if plan.time_utilization_ratio is None else f"{plan.time_utilization_ratio:.3f}"))
        lines.append("Estimated Max Single Leg: " + ("-" if plan.estimated_max_single_leg_km is None else f"{plan.estimated_max_single_leg_km:.3f} km"))
    lines.extend("Error: " + user_text(e, repo) for e in result.errors)
    return "\n".join(lines)


def resolve_infeasible(service, intent, result):
    for _ in range(8):
        if result.feasibility is None or result.feasibility.feasible:
            return result
        print(render_result(result, service.repo))
        print("\n1. Extend my time\n2. Keep my time and help me choose\n3. Edit selected places\n0. Stop")
        action = input("> ").strip()
        if action == "0":
            return result
        if action == "1":
            intent.available_minutes = int(input("New available minutes: "))
        elif action == "3":
            show_catalog(service.repo)
            intent.must_go_poi_ids = service.resolver.select_pois(selections(input("Selected places: ")))
            intent.visit_mode_overrides = {pid: mode for pid, mode in intent.visit_mode_overrides.items() if pid in intent.must_go_poi_ids}
        elif action == "2":
            proposals = service.feasibility.suggest_subsets(intent, FeasibilityAction.HELP_ME_CHOOSE)
            if not proposals:
                print("No selected subset fits. Increase time or choose a closer start.")
                continue
            for index, proposal in enumerate(proposals, 1):
                print(f"{index}. Keep: " + ", ".join(service.repo.get_poi_by_id(pid).name_en for pid in proposal.keep_poi_ids)
                      + f"; estimate {proposal.estimated_minutes:.2f} min")
                print("   Remove: " + ", ".join(service.repo.get_poi_by_id(pid).name_en for pid in proposal.remove_poi_ids))
            selected = int(input("Proposal number (0 cancels): "))
            if selected == 0:
                continue
            if not 1 <= selected <= len(proposals):
                raise RequestValidationError("Unknown proposal")
            if input("Confirm changing selected places? Type yes: ").strip().casefold() == "yes":
                intent = service.feasibility.confirm_subset(intent, proposals[selected-1], confirmed=True)
        else:
            raise RequestValidationError("Unknown feasibility action")
        intent = read_clarifications(service, intent)
        result = service.generate(intent)
    return result


def main(argv=None, *, live=False):
    parser = argparse.ArgumentParser(description="ShanghaiTrace Phase 2 entry demo")
    parser.add_argument('--kb', choices=KB_NAMES, default='production',
                        help='Explicit POI KB selection (default: production; candidate is never promoted)')
    parser.add_argument("--mode", choices=list(RouteMode))
    parser.add_argument("--text")
    parser.add_argument("--places", help="Semicolon-separated catalog names or display numbers")
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--start")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-places", action="store_true")
    args = parser.parse_args(argv)
    menu = args.mode is None and not args.list_places
    interactive = menu or (args.mode == RouteMode.PLAN_FOR_ME and not args.json)
    summary = {}
    try:
        repo = resolve_poi_repository(args.kb, repository_factory=POIRepository)
        summary = kb_summary(args.kb, repo)
        if not args.json or args.list_places:
            print(render_kb_summary(summary), flush=True)
        client = DeepSeekLLMClient() if live else MockLLMClient(fixtures=PLAN_EXAMPLES)
        service = RouteEntryService(repo, client)
        if args.list_places:
            show_catalog(repo)
            return 0
        if menu:
            print("How would you like to explore Shanghai?\n1. Plan for me\n2. I have places in mind\n3. Surprise me")
            choice = input("> ").strip()
            modes = {"1": RouteMode.PLAN_FOR_ME, "2": RouteMode.PLACES_IN_MIND, "3": RouteMode.SURPRISE_ME}
            if choice not in modes:
                raise RequestValidationError("Choose 1, 2 or 3")
            mode = modes[choice]
        else:
            mode = RouteMode(args.mode)
        if mode == RouteMode.PLAN_FOR_ME:
            if not live and not args.json:
                print("Offline mock: exact sample fixtures only. For arbitrary natural language, use tools/demos/chat_demo.py.")
            text = args.text or (input("Tell me what kind of walk you'd like:\n> ") if interactive else "")
            intent = service.parse_plan(text)
            if args.minutes is not None:
                intent.available_minutes = args.minutes
            if args.start is not None:
                intent.start_location_text, intent.start_lat, intent.start_lng = args.start, None, None
        elif mode == RouteMode.PLACES_IN_MIND:
            if interactive:
                show_catalog(repo)
            places = args.places or (input("Selected places: ") if interactive else "")
            intent = service.places_intent(selections(places), args.minutes, start_location_text=args.start)
        else:
            start = args.start or (input("Where would you like to start?\n> ") if interactive else None)
            intent = RouteIntent(mode, start_location_text=start, available_minutes=args.minutes, surprise_seed=args.seed)
        if interactive:
            print(render_intent(service.clarification.prepare(intent), repo))
            intent = read_clarifications(service, intent)
        result = service.generate(intent)
        if interactive or (mode == RouteMode.SURPRISE_ME and not args.json):
            result = resolve_infeasible(service, result.intent, result)
            if result.status == 'needs_route_quality_clarification':
                print(render_result(result, repo))
                print(result.route_quality.question)
                for index, option in enumerate(result.route_quality.options, 1):
                    print(f"{index}. {option.label}")
                result = service.answer_route_quality_clarification(result, input('> '))
        # JSON remains one parseable document; KB information leads the object.
        print(json.dumps({**summary, **result.to_dict()}, ensure_ascii=False, indent=2) if args.json else render_result(result, repo))
        return 0 if result.status in ("success", "needs_clarification", "needs_route_quality_clarification") else 1
    except LLMClientError as exc:
        print(json.dumps({**summary, 'status': 'provider_error', 'errors': [str(exc)], 'error_type': exc.kind,
                          'stage': exc.stage, 'http_status': exc.http_status, 'finish_reason': exc.finish_reason},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    except (RequestValidationError, DataValidationError, ValueError) as exc:
        print(json.dumps({**summary, "status": "validation_error", "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("Input ended; no further selection changes made.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Unified minimum viable walk check; never fills stops or changes scoring."""
import copy
import re
from collections import Counter

from .intent_models import ClarificationOption, RouteMode, RouteQualityAssessment
from .models import RequestValidationError
from .poi_repository import TAG_GROUPS
from .visit_planner import VisitPlanner
from .intent_adapter import intent_to_route_request

MINIMUM_VIABLE_STOPS = 3
PREFERENCE_SUGGESTION = 'Broaden one preference, allow a compatible theme, or broaden the selected area.'


def eligible_catalog(intent, repository, zone=None):
    request = intent_to_route_request(intent)
    planner = VisitPlanner()
    return [p for p in repository.get_all_pois() if p.coordinates is not None
            and (zone is None or p.zone_id == zone)
            and p.id not in intent.avoid_poi_ids
            and not set(intent.avoid_tags).intersection(t for g in TAG_GROUPS for t in getattr(p, g))
            and planner.resolve(p, request) is not None]


def needs_route_quality_clarification(intent, plan, availability):
    return (intent.route_mode in (RouteMode.PLAN_FOR_ME, RouteMode.SURPRISE_ME)
            and plan.status in ('success', 'infeasible', 'no_feasible_route_found')
            and len(plan.ordered_pois) < MINIMUM_VIABLE_STOPS)


def assess_route_quality(intent, plan, availability, repository):
    required = needs_route_quality_clarification(intent, plan, availability)
    assessment = RouteQualityAssessment(
        status='clarification_required' if required else 'passed',
        minimum_required_stops=MINIMUM_VIABLE_STOPS,
        minimum_viable=len(plan.ordered_pois) >= MINIMUM_VIABLE_STOPS,
        available_minutes=intent.available_minutes, actual_stops=len(plan.ordered_pois),
        preferred_min_stops=(plan.richness_target or {}).get('min_stops'),
        time_utilization_ratio=plan.time_utilization_ratio or 0.0,
        remaining_minutes=plan.remaining_minutes if plan.remaining_minutes is not None else intent.available_minutes,
        candidate_availability=availability)
    if not required:
        return assessment
    assessment.reasons = ['no_eligible_candidates' if availability['matching_same_zone'] == 0
                          else 'insufficient_viable_stops']
    zone = intent.preferred_zone or plan.selected_zone
    points = eligible_catalog(intent, repository, zone)
    counts = Counter(t for p in points for t in p.interest_tags
                     if t not in intent.interest_tags and t not in intent.avoid_tags)
    # Prioritize themes with actual eligible inventory; stable taxonomy names break ties.
    zone_name = next((z['name_en'] for z in repository.get_raw_data()['metadata']['walk_zones'] if z['id'] == zone), '')
    themes = sorted(counts, key=lambda tag: (not bool(re.search(r'\b'+re.escape(tag.replace('_', ' '))+r'\b', zone_name, re.I)),
                                            -counts[tag], tag))[:2]
    labels = {'waterfront': 'Add waterfront scenery', 'industrial_heritage': 'Add industrial heritage',
              'architecture': 'Add historic architecture'}
    assessment.options = [ClarificationOption(labels.get(t, 'Add '+t.replace('_', ' ')), t) for t in themes]
    if intent.preferred_zone is not None and any(p.zone_id != intent.preferred_zone
                                               for p in eligible_catalog(intent, repository)):
        assessment.options.append(ClarificationOption('Broaden beyond the selected area', 'broaden_area'))
    assessment.options.append(ClarificationOption('Keep my current preferences', 'strict'))
    assessment.question = ('I found fewer than three suitable stops under your current preferences, '
                           'which is not enough for a complete City Walk. Would you like to broaden a theme or area?')
    return assessment


def merge_quality_choice(intent, assessment, text):
    if assessment.clarification_applied or assessment.status != 'clarification_required':
        raise RequestValidationError('Route-quality clarification is already completed or was not requested')
    answer = str(text).strip().casefold()
    selected = next((o for index, o in enumerate(assessment.options, 1)
                     if answer in (str(index), str(o.value).casefold(), o.label.casefold())), None)
    if selected is None:
        raise RequestValidationError('Choose one of the displayed route-quality options')
    merged = copy.deepcopy(intent)
    if selected.value == 'broaden_area':
        merged.preferred_zone = None
    elif selected.value != 'strict':
        merged.interest_tags = list(dict.fromkeys(merged.interest_tags + [selected.value]))
    return merged, selected.value

"""Three inputs, one intent contract, one adapter and one existing route engine."""

import copy

from .clarification import ClarificationLayer
from .feasibility import FeasibilityChecker
from .intent_adapter import intent_to_route_request
from .intent_models import RouteMode, RouteIntent, EntryResult
from .intent_parser import IntentParser
from .intent_schema import route_intent_schema, validate_json
from .location_resolver import LocationResolver
from .models import RequestValidationError, RoutePlan
from .route_engine import RouteEngine
from .surprise_policy import SurpriseRoutePolicy
from .route_quality import assess_route_quality, merge_quality_choice, PREFERENCE_SUGGESTION


class RouteEntryService:
    def __init__(self, repository, llm_client=None, *, walking_service=None):
        self.repo = repository
        self.engine = RouteEngine(repository)
        from .services.walking_route_service import default_walking_service
        self.walking_service = walking_service if walking_service is not None else default_walking_service()
        self.resolver = LocationResolver(repository)
        self.clarification = ClarificationLayer(repository, self.resolver)
        self.feasibility = FeasibilityChecker(repository)
        self.surprise = SurpriseRoutePolicy(repository, self.engine)
        self.parser = None if llm_client is None else IntentParser(repository, llm_client, self.clarification, self.resolver)

    def parse_plan(self, text):
        if self.parser is None:
            raise RequestValidationError("Plan for me needs an explicitly configured LLM client or mock")
        return self.parser.parse(text)

    def places_intent(self, selections, available_minutes=None, **fields):
        try:
            ids = self.resolver.select_pois(selections)
        except ValueError as exc:
            raise RequestValidationError(str(exc)) from exc
        return self.clarification.prepare(RouteIntent(RouteMode.PLACES_IN_MIND,
            available_minutes=available_minutes, must_go_poi_ids=ids, **fields))

    def answer_clarification(self, intent, field, text):
        try:
            answer = self.clarification.parse_answer_text(intent, field, text)
        except RequestValidationError:
            raise
        except ValueError:
            if self.parser is None:
                raise RequestValidationError("Use one of the displayed choices or a structured value") from None
            return self.parser.answer_text(intent, field, text)
        return self.clarification.answer(intent, {field: answer})

    def generate(self, intent):
        result = self._generate(intent)
        if (result.intent.route_mode in (RouteMode.PLAN_FOR_ME, RouteMode.SURPRISE_ME)
                and result.status in ('success', 'infeasible', 'no_feasible_route_found')
                and not (result.feasibility and not result.feasibility.feasible)):
            if result.route_plan is None:
                result.route_plan = RoutePlan(result.status, vars(intent_to_route_request(result.intent)),
                                              errors=list(result.errors), selected_zone=result.intent.preferred_zone)
            result.route_quality = self.generate_assessment(result)
            if result.route_quality.status == 'clarification_required':
                result.status = 'needs_route_quality_clarification'
        if result.status == 'success' and result.route_plan is not None:
            result.route_plan = self.walking_service.hydrate_walking_route(result.route_plan)
        return result

    def answer_route_quality_clarification(self, result, text):
        if (result.status != 'needs_route_quality_clarification' or result.route_quality is None
                or result.route_plan is None):
            raise RequestValidationError('No pending route-quality clarification')
        merged, choice = merge_quality_choice(result.intent, result.route_quality, text)
        if choice == 'strict':
            final = copy.deepcopy(result)
            final.status = final.route_plan.status
            final.warnings.append('The route remains intentionally short because you chose to keep the preference profile narrow.')
        else:
            # Re-plan once, without scheduling another quality question.
            if merged.route_mode == RouteMode.SURPRISE_ME:
                plan = self.engine.generate_route(intent_to_route_request(merged))
                final = EntryResult(plan.status, merged, plan, result.feasibility, result.surprise_theme,
                                    warnings=list(result.warnings))
            else:
                final = self._generate(merged)
        final.route_quality = (self.generate_assessment(final) if final.route_plan is not None
                               else copy.deepcopy(result.route_quality))
        if final.route_quality.actual_stops < final.route_quality.minimum_required_stops:
            final.status = 'insufficient_route'
            if final.route_plan is not None:
                final.route_plan.status = 'insufficient_route'
                if final.route_quality.candidate_availability.get('matching_same_zone', 0) < 3:
                    final.route_plan.relaxation_suggestions = [PREFERENCE_SUGGESTION]
                final.route_plan.explanation = ('No eligible POIs matched the current zone, interests and avoidance preferences.'
                    if final.route_quality.reasons == ['no_eligible_candidates'] else
                    f'I found only {final.route_quality.actual_stops} suitable stops. A complete City Walk requires at least three route anchors.')
        final.route_quality.status = 'accepted_strict' if choice == 'strict' else 'replanned'
        final.route_quality.clarification_applied = True
        final.route_quality.preference_broadening = 'declined' if choice == 'strict' else choice
        # Final assessment records minimum viability after the one permitted answer.
        final.route_quality.question = None
        final.route_quality.options = []
        if final.status == 'success' and final.route_plan is not None:
            final.route_plan = self.walking_service.hydrate_walking_route(final.route_plan)
        return final

    def generate_assessment(self, result):
        request = intent_to_route_request(result.intent)
        eligible = [p for p in self.repo.get_all_pois() if p.coordinates is not None
                    and (result.route_plan.selected_zone is None or p.zone_id == result.route_plan.selected_zone)
                    and (p.id in request.must_go_poi_ids or not self.engine._avoided(p, request))
                    and self.engine.visits.resolve(p, request) is not None]
        availability = dict(eligible_same_zone=len(eligible), matching_same_zone=sum(self.engine._relevant(p, request) for p in eligible))
        if availability['matching_same_zone'] == 0:
            reason = 'No eligible POIs matched the current zone, interests and avoidance preferences.'
            result.route_plan.errors = [reason]
            result.route_plan.explanation = reason
            result.route_plan.relaxation_suggestions = [PREFERENCE_SUGGESTION]
            result.errors = []
        return assess_route_quality(result.intent, result.route_plan, availability, self.repo)

    def _generate(self, intent):
        if isinstance(intent, dict):
            validate_json(intent, route_intent_schema(self.repo))
            intent = RouteIntent.from_dict(intent)
        validate_json(intent.to_dict(), route_intent_schema(self.repo))
        prepared = self.clarification.prepare(intent)
        if prepared.needs_clarification:
            return EntryResult("needs_clarification", prepared, warnings=prepared.warnings)
        check = None
        # Explicit must-go requests receive preflight even if entered in natural language.
        if prepared.must_go_poi_ids:
            check = self.feasibility.check(prepared)
            if not check.feasible:
                return EntryResult(check.status, prepared, feasibility=check, warnings=prepared.warnings + check.warnings)
        if prepared.route_mode == RouteMode.SURPRISE_ME:
            selected = self.surprise.choose(prepared)
            if selected is None:
                return EntryResult("no_feasible_route_found", prepared, warnings=prepared.warnings,
                    errors=["No curated walking route fits this start, time and distance budget. Try a closer start or more time."])
            curated, theme, plan = selected
            return EntryResult(plan.status, curated, plan, check, theme, prepared.warnings)
        plan = self.engine.generate_route(intent_to_route_request(prepared))
        return EntryResult(plan.status, prepared, plan, check,
                           warnings=prepared.warnings + ([] if check is None else check.warnings))

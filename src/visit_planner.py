"""Select visit mode and estimate duration without equating full_visit to indoors."""

from .models import SelectedVisit


class VisitPlanner:
    def resolve(self, poi, request):
        mode = request.visit_mode_overrides.get(poi.id, poi.visit_profile.default_mode)
        reason = None
        if mode == "full_visit":
            if poi.id in request.full_visit_unavailable_poi_ids:
                reason = "full_visit_unavailable"
            elif not request.willing_to_buy_tickets and poi.visit_mode_details[mode]["ticket_required"] is True:
                reason = "user_declines_ticket"
        if reason:
            if request.allow_mode_downgrade and "walk_stop" in poi.visit_profile.supported_modes:
                return SelectedVisit(poi, "walk_stop", request.travel_pace, mode, reason)
            return None
        return SelectedVisit(poi, mode, request.travel_pace, mode)

    def budget_fallback(self, visit, request):
        if (request.allow_mode_downgrade and visit.selected_visit_mode == "full_visit"
                and "walk_stop" in visit.visit_profile.supported_modes):
            alternative = SelectedVisit(visit.poi, "walk_stop", request.travel_pace,
                                        visit.requested_visit_mode, "insufficient_time")
            if alternative.stay_minutes < visit.stay_minutes:
                return alternative
        return None

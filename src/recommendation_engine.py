"""Independent, configuration-driven scoring and template explanations."""

from .poi_repository import TAG_GROUPS


class RecommendationEngine:
    def __init__(self, repository):
        self.weights = dict(repository.defaults["scoring_weights"])

    def matched_tags(self, poi, request):
        return {g: sorted(set(getattr(poi, g)) & set(getattr(request, g))) for g in TAG_GROUPS}

    def tag_score(self, poi, request):
        matches = self.matched_tags(poi, request)
        return sum(len(matches[g]) * self.weights[w] for g, w in zip(
            TAG_GROUPS, ("interest_tag_match", "experience_tag_match", "culture_tag_match")))

    def score(self, poi, request, selected_zone, distance_km):
        return (self.tag_score(poi, request)
                + (self.weights["same_zone_bonus"] if poi.zone_id == selected_zone else 0)
                - distance_km * self.weights["distance_penalty_per_km"])

    def preference_key(self, poi, request):
        preferred = request.environment_preference
        environment = 0 if preferred in (None, "mixed") or poi.environment == preferred else (1 if poi.environment == "mixed" else 2)
        crowd = {"low": 0, "medium": 1, None: 2, "high": 3}[poi.crowd_level] if request.avoid_crowds else 0
        return environment, crowd

    def explanation(self, poi, request, selected_zone):
        matched = self.matched_tags(poi, request)
        flattened = [t for group in TAG_GROUPS for t in matched[group]]
        reason = f"Recommended because it matches: {', '.join(flattened)}." if flattened else "Recommended as a nearby stop; no requested tag matches."
        if poi.id in request.must_go_poi_ids:
            reason = "Included because you marked it as must-go. " + reason
        reason += f" Located in {poi.zone_name_en}."
        if poi.zone_id != selected_zone:
            reason += " This required stop involves walking outside the primary zone."
        return reason

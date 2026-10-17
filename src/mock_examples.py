"""Documented exact fixtures for offline CLI demos; not a natural-language parser."""


def candidate(**overrides):
    result = {"available_minutes": None, "start_location_text": None, "interest_tags": [],
              "experience_tags": [], "culture_tags": [], "travel_pace": "standard",
              "preferred_zone": None, "max_walking_km": None, "must_go_place_names": [],
              "avoid_tags": [], "avoid_place_names": [], "unresolved_negative_preferences": []}
    result.update(overrides)
    return result


PLAN_EXAMPLES = {
    "I have three hours and want old Shanghai architecture and local neighborhoods.": candidate(
        available_minutes=180, interest_tags=["architecture", "local_life"], experience_tags=["neighborhood_walk"]),
    "I have three hours and want to see old architecture and local neighborhoods.": candidate(
        available_minutes=180, interest_tags=["architecture", "local_life"], experience_tags=["neighborhood_walk"]),
    "I want a relaxed literary walk around Lu Xun's neighborhood for two hours.": candidate(
        available_minutes=120, interest_tags=["literature"], experience_tags=["quiet_walk"], preferred_zone="hongkou_literary"),
    "Plan a walk for me.": candidate(),
    "I want to see old Shanghai.": candidate(interest_tags=["history"]),
    "I have three hours.": candidate(available_minutes=180),
    "I just want the highlights for two hours, focused on architecture.": candidate(
        available_minutes=120, interest_tags=["architecture"], travel_pace="quick"),
    "I have three hours and want to take my time and understand the history.": candidate(
        available_minutes=180, interest_tags=["history"], travel_pace="deep"),
    "I want to see the more authentic side of Shanghai.": candidate(interest_tags=["local_life"]),
    "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.": candidate(
        available_minutes=150, interest_tags=["local_life"], experience_tags=["neighborhood_walk"], avoid_tags=["museum_visit"]),
    "I have three hours and want old architecture and local neighborhoods.": candidate(
        available_minutes=180, interest_tags=["architecture", "local_life"], experience_tags=["neighborhood_walk"]),
}

"""Exact offline extraction fixtures; routes always come from RouteEntryService."""
from .mock_examples import PLAN_EXAMPLES, candidate
from .trip_command_fixtures import TRIP_COMMAND_FIXTURES, proposal
from .trip_action_fixtures import ACTION_FIXTURES

FULL_JOURNEY_INITIAL = 'I have three hours and want architecture, industrial heritage and river views around West Bund.'
INITIAL_EXAMPLE = 'I have three hours and want to explore architecture and local neighborhoods.'
INITIAL_CLARIFICATION = 'Three hours, mainly architecture and local life.'
AGENT_FIXTURES = dict(PLAN_EXAMPLES, **TRIP_COMMAND_FIXTURES)
AGENT_FIXTURES.update({
    FULL_JOURNEY_INITIAL: candidate(available_minutes=180, interest_tags=['architecture', 'industrial_heritage', 'waterfront'], experience_tags=['riverside_walk'], preferred_zone='west_bund', start_location_text='West Bund'),
    INITIAL_EXAMPLE: candidate(available_minutes=180, interest_tags=['architecture', 'local_life'], experience_tags=['neighborhood_walk']),
    'I want to explore Shanghai.': candidate(),
    INITIAL_CLARIFICATION: candidate(available_minutes=180, interest_tags=['architecture', 'local_life'], experience_tags=['neighborhood_walk']),
    'Show me my original route.': proposal('read_query', read_query='show_original_route'),
    "I'm a little tired, I only have one hour left, and I don't want to visit museums anymore.": proposal(remaining_minutes=60, pace='deep', add_avoid_tags=['museum_visit'], request_replan=True),
    'Actually, I only have two hours now.': proposal(remaining_minutes=120, request_replan=True),
})
AGENT_FIXTURES.update(ACTION_FIXTURES)

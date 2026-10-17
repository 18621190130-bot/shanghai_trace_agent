"""Explicit offline examples, not a natural-language model or network fallback."""
from .trip_commands import TripCommandProposal


def proposal(command_type='replan_change', **fields):
    return TripCommandProposal(command_type=command_type, **fields).to_dict()


TRIP_COMMAND_FIXTURES = {}


def add(texts, value):
    for text in texts:TRIP_COMMAND_FIXTURES[text] = value


add(["I'm a little tired.", "I'm a little tired. Let's take it easy.", '我有点累了，慢一点吧。'],
    proposal(pace='deep', request_replan=True))
add(['I only have one hour left.', 'I need to leave in an hour.', '我只剩一个小时了。'],
    proposal(remaining_minutes=60, request_replan=True))
add(['I only have 45 minutes left.'], proposal(remaining_minutes=45, request_replan=True))
add(['我四十分钟后要走。'], proposal(remaining_minutes=40, request_replan=True))
add(["I don't want to visit museums anymore.", '接下来别安排博物馆了。'],
    proposal(add_avoid_tags=['museum_visit'], request_replan=True))
add(['Museums are fine again.', "Actually, I don't mind museums now.", '可以去博物馆了。'],
    proposal(remove_avoid_tags=['museum_visit'], request_replan=True))
add(["I'd like to see more architecture.", '接下来更想看老建筑。', 'I still want architecture.'],
    proposal(add_interest_tags=['architecture'], request_replan=True))
add(["I'd like to see more old architecture and local neighborhoods."],
    proposal(add_interest_tags=['architecture', 'local_life'], request_replan=True))
add(["I don't care about architecture anymore."], proposal(remove_interest_tags=['architecture'], request_replan=True))
add(["I only have an hour left, I'm tired, and I don't want museums anymore."],
    proposal(remaining_minutes=60, pace='deep', add_avoid_tags=['museum_visit'], request_replan=True))
add(['Skip this place.', 'Skip this stop.', '跳过这个地方。'],
    proposal('core_action', core_action='skip_stop', place_reference='this place', request_replan=True))
add(['Skip this place, and I only have 45 minutes left.'],
    proposal('core_action', core_action='skip_stop', place_reference='this place', remaining_minutes=45, request_replan=True))
add(["I've finished this stop.", "I'm done here.", '这个地方逛完了。'],
    proposal('core_action', core_action='complete_stop', place_reference='this stop'))
add(['I want to visit Wukang Mansion.', 'I definitely want to visit Wukang Mansion.'],
    proposal(must_go_place_mentions=['Wukang Mansion'], request_replan=True))
add(['我一定想去武康大楼。'], proposal(must_go_place_mentions=['武康大楼'], request_replan=True))
add(['I want to visit West Bund Art Center.'],
    proposal(must_go_place_mentions=['West Bund Art Center'], request_replan=True))
add(['I want to visit the old residence.'],
    proposal(must_go_place_mentions=['old residence'], request_replan=True))
add(['I want to visit Unknown Imaginary Tower.'],
    proposal(must_go_place_mentions=['Unknown Imaginary Tower'], request_replan=True))
for query, texts in {
    'why_latest_replan': ['Why did you change my route?', '刚刚为什么改路线？'],
    'show_original_route': ['Show me the original route.', '给我看看最初路线。'],
    'show_current_route': ['What is my current route?', '现在的路线是什么？'],
    'show_route_history': ['What changes have been made to my route?', '路线之前改过哪些地方？'],
}.items():add(texts, proposal('read_query', read_query=query))
add(['Take me somewhere interesting.', 'Skip that place.', "I don't want this kind of place.", 'This museum was boring.'],
    proposal('ambiguous', needs_clarification=True, clarification_reason='vague_change'))
add(['Replan my remaining route.'], proposal(request_replan=True))

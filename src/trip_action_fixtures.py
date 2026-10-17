"""Offline extraction examples and a small human-run live acceptance corpus.

Fixtures test protocol/execution, not a claim that a language model understood text.
"""
from .trip_actions import TripActionProposal, TripUtteranceProposal
from .trip_command_fixtures import TRIP_COMMAND_FIXTURES


def action(kind, **fields):return TripActionProposal(kind, **fields)
def utterance(*actions, **fields):return TripUtteranceProposal(list(actions), **fields).to_dict()


def legacy_fixture(value):
    """Data migration for old OFFLINE fixtures only, never for live provider output."""
    actions = []
    if value['command_type'] == 'read_query':
        return utterance(action(value['read_query'].upper()))
    if value['command_type'] == 'unsupported':return utterance(action('UNSUPPORTED'))
    if value.get('core_action'):
        kinds = {'complete_stop': 'COMPLETE_STOP', 'skip_stop': 'SKIP_PLACE', 'update_elapsed_time': 'UNSUPPORTED'}
        actions.append(action(kinds[value['core_action']], target_mentions=[value['place_reference']] if value.get('place_reference') else []))
    for field, kind in [('add_interest_tags', 'ADD_INTEREST'), ('remove_interest_tags', 'REMOVE_INTEREST'),
                        ('add_avoid_tags', 'ADD_AVOID'), ('remove_avoid_tags', 'REMOVE_AVOID')]:
        if value.get(field):actions.append(action(kind, preference_tags=value[field]))
    for name in value.get('must_go_place_mentions', []):actions.append(action('ADD_PLACE', target_mentions=[name]))
    if value.get('remaining_minutes') is not None:actions.append(action('SET_HARD_TIME_LIMIT', time_value_minutes=value['remaining_minutes'], time_constraint_mode='hard'))
    if value.get('pace'):actions.append(action('SET_PACE', pace=value['pace']))
    return utterance(*(actions or [action('SET_TIME_TARGET')]), needs_clarification=value.get('needs_clarification', False),
                     clarification_reason=value.get('clarification_reason'))


ACTION_FIXTURES = {text: legacy_fixture(value) for text, value in TRIP_COMMAND_FIXTURES.items()}
ACCEPTANCE_CASES = []


def examples(category, texts, *actions):
    for text in texts:
        proposal = utterance(*actions)
        ACTION_FIXTURES[text] = proposal
        ACCEPTANCE_CASES.append(dict(category=category, text=text, expected=proposal))


examples('REMOVE', ['Skip this place.', 'nah, skip it', '这个点跳过。'], action('SKIP_PLACE', target_mentions=['this place']))
examples('REMOVE', ["I don't want to go to West Bund Museum anymore.", 'Remove West Bund Museum.', "Let's take West Bund Museum off the route.", '西岸美术馆我不想去了。'], action('REMOVE_PLACE', target_mentions=['West Bund Museum']))
examples('REMOVE', ['这个不去了。'], action('REMOVE_PLACE', target_mentions=['this place']))
examples('ADD', ['Add Long Museum.', 'Add Long Museum to my route.', 'Can we include Long Museum?', '龙美术馆也安排一下。'], action('ADD_PLACE', target_mentions=['Long Museum']))
examples('MUST_GO', ['Make sure we visit Long Museum.', "I'd really like to see Long Museum.", '龙美术馆我一定想去。'], action('ADD_MUST_GO', target_mentions=['Long Museum']))
examples('REVISIT', ['I want to visit TANK Shanghai again.', "Let's return to TANK Shanghai.", 'Can we return to TANK Shanghai?', '我们再去一次TANK Shanghai。'], action('REVISIT_PLACE', target_mentions=['TANK Shanghai']))
examples('REVISIT', ['I want to go there again.', '刚才那个地方我还想再看看。'], action('REVISIT_PLACE', target_mentions=['there']))
examples('REPLACE', ['Replace this place.', 'Skip this place and find me another one.', '这个不去了，换一个。'], action('REPLACE_PLACE', target_mentions=['this place']))
examples('REORDER', ['Can we go to Long Museum next?', 'Go to Long Museum next.', '龙美术馆下一站去。'], action('MOVE_PLACE_NEXT', target_mentions=['Long Museum'], position_relation='next'))
examples('REORDER', ['Put Long Museum before West Bund Museum.'], action('MOVE_PLACE_BEFORE', target_mentions=['Long Museum'], secondary_target_mentions=['West Bund Museum'], position_relation='before'))
examples('PREFERENCE', ["I don't want museums anymore.", '博物馆不去了。'], action('ADD_AVOID', preference_tags=['museum_visit'], preference_concepts=['museums']))
examples('REMOVE', ["I don't want West Bund Museum anymore."], action('REMOVE_PLACE', target_mentions=['West Bund Museum']))
examples('PREFERENCE', ["I'd like more architecture.", '我想多看一些建筑。'], action('ADD_INTEREST', preference_tags=['architecture'], preference_concepts=['architecture'], request_matching_insert=True))
examples('REVERSAL', ['Actually, museums are fine again.', 'Forget the museum restriction.', '博物馆也可以。'], action('REMOVE_AVOID', preference_tags=['museum_visit']))
examples('REVERSAL', ['Actually, keep West Bund Museum.'], action('ADD_PLACE', target_mentions=['West Bund Museum']))
examples('TIME', ['I have about an hour.', 'I want to walk for another hour.'], action('SET_TIME_TARGET', time_value_minutes=60, time_constraint_mode='soft'))
examples('TIME', ['I only have one hour left.', 'I have one hour left.', 'I can only stay another hour.', '我只剩一个小时了。', 'I have about one hour left before I need to leave.'], action('SET_HARD_TIME_LIMIT', time_value_minutes=60, time_constraint_mode='hard'))
examples('TIME', ["I've only got 45 minutes left."], action('SET_HARD_TIME_LIMIT', time_value_minutes=45, time_constraint_mode='hard'))
examples('TIME', ['I have another 30 minutes before I need to go.', '最多只能再逛半小时。'], action('SET_HARD_TIME_LIMIT', time_value_minutes=30, time_constraint_mode='hard'))
examples('TIME', ['我还有四十分钟就要走了。'], action('SET_HARD_TIME_LIMIT', time_value_minutes=40, time_constraint_mode='hard'))
examples('TIME', ["I'd like to spend about another hour.", "Let's aim for around one hour.", "Maybe another hour, but there's no rush.", '我想再逛大概一个小时。', '最好控制在一小时左右，不过不用赶。', "I'd like to spend about another hour, but there's no rush."], action('SET_TIME_TARGET', time_value_minutes=60, time_constraint_mode='soft'))
examples('TIME', ['I must leave in one hour.', 'Make sure this fits within 60 minutes.', '必须在一个小时内结束。'], action('SET_HARD_TIME_LIMIT', time_value_minutes=60, time_constraint_mode='hard'))
examples('COMPOUND', ["Skip this museum, add Long Museum, and I'd like more architecture."],
         action('SKIP_PLACE', target_mentions=['this museum']), action('ADD_PLACE', target_mentions=['Long Museum']), action('ADD_INTEREST', preference_tags=['architecture'], request_matching_insert=True))
examples('COMPOUND', ['Remove this stop and put Long Museum next.'], action('REMOVE_PLACE', target_mentions=['this stop']),
         action('ADD_PLACE', target_mentions=['Long Museum']), action('MOVE_PLACE_NEXT', target_mentions=['Long Museum'], position_relation='next'))
examples('NEGATION', ["I don't dislike museums."], action('REMOVE_AVOID', preference_tags=['museum_visit']))
examples('NEGATION', ["I don't want to skip this place."], action('ADD_PLACE', target_mentions=['this place']))
examples('NEGATION', ["I don't want museums, but I still want Long Museum.", "I don't want museums except Long Museum."],
         action('ADD_AVOID', preference_tags=['museum_visit']), action('ADD_MUST_GO', target_mentions=['Long Museum']))
examples('READ', ['What is my current route?'], action('SHOW_CURRENT_ROUTE'))
examples('READ', ['Show me my original route.'], action('SHOW_ORIGINAL_ROUTE'))
examples('READ', ['Why did you change my route?'], action('WHY_LATEST_REPLAN'))
examples('READ', ['What changes have been made to my route?'], action('SHOW_ROUTE_HISTORY'))
examples('READ', ['How many stops are left?'], action('SHOW_PROGRESS'))
examples('FULL', ['Replan the rest of my route.', '重新规划剩下路线。'], action('FULL_REPLAN', explicit_replan=True))
for text, kind, mode in [("I'd like to finish around 5.", 'SET_TIME_TARGET', 'soft'), ('I need to be done by 5 PM.', 'SET_HARD_TIME_LIMIT', 'hard')]:
    value = utterance(action(kind, time_constraint_mode=mode), needs_clarification=True, clarification_reason='duration_required')
    ACTION_FIXTURES[text] = value;ACCEPTANCE_CASES.append(dict(category='TIME', text=text, expected=value))
ACTION_FIXTURES.update({
    'Replan my remaining route.': utterance(action('FULL_REPLAN', explicit_replan=True)),
    'Replan the remaining route completely.': utterance(action('FULL_REPLAN', explicit_replan=True)),
    'Actually, I only have two hours now.': utterance(action('SET_HARD_TIME_LIMIT', time_value_minutes=120, time_constraint_mode='hard')),
    "I'm a little tired, I only have one hour left, and I don't want to visit museums anymore.": utterance(action('SET_PACE', pace='deep'), action('SET_HARD_TIME_LIMIT', time_value_minutes=60, time_constraint_mode='hard'), action('ADD_AVOID', preference_tags=['museum_visit'])),
    'I really want to visit West Bund Art Center.': utterance(action('ADD_MUST_GO', target_mentions=['West Bund Art Center'])),
    "I'd like to see more architecture.": utterance(action('ADD_INTEREST', preference_tags=['architecture'], request_matching_insert=True)),
    'I want to stay here longer.': utterance(action('DWELL_LONGER', dwell_preference='increase_current_stop_dwell')),
    "I'd like to finish earlier.": utterance(action('SET_TIME_TARGET'), needs_clarification=True, clarification_reason='duration_required'),
    'I must finish within one hour.': utterance(action('SET_HARD_TIME_LIMIT', time_value_minutes=60, time_constraint_mode='hard')),
})

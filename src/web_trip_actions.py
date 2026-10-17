"""Web controls use the existing validated action executor, not a second planner."""
from .trip_actions import TripActionProposal, TripUtteranceProposal, normalize_actions
from .trip_conversation import ConversationalTripService


class ExplicitControlParser:
    """A button supplies a typed action; natural-language requests use the real LLM."""
    def __init__(self, proposal):self.proposal=proposal;self.last_trace={}
    def parse(self, text, context):return self.proposal


def execute_control(app, session, body):
    allowed={'SHORTEN_ROUTE','ADD_MATCHING_STOPS','SKIP_PLACE','ADD_MUST_GO','ADD_PLACE','REMOVE_PLACE','REPLACE_PLACE','MOVE_PLACE_NEXT',
             'MOVE_PLACE_BEFORE','MOVE_PLACE_AFTER','SET_PACE','SET_TIME_TARGET',
             'SET_HARD_TIME_LIMIT','ADD_INTEREST','REMOVE_INTEREST','ADD_AVOID','REMOVE_AVOID','FULL_REPLAN'}
    kind=body.get('kind')
    if kind not in allowed:raise ValueError('invalid_input')
    trip=app.trips.get_trip(session['trip_id'])
    def names(key):
        ids=body.get(key,[])
        if not isinstance(ids,list) or len(ids)>1:raise ValueError('invalid_input')
        result=[]
        for pid in ids:
            poi=app.repo.get_poi_by_id(pid)
            if poi.zone_id!=trip.active_route['selected_zone']:raise ValueError('zone_mismatch')
            result.append(poi.name_zh)
        return result
    tags=body.get('tags',[])
    if not isinstance(tags,list) or any(t not in {t for group in app.repo.taxonomy.values() for t in group} for t in tags):raise ValueError('invalid_input')
    minutes=body.get('minutes')
    if minutes is not None and (type(minutes) not in (int,float) or not 0<minutes<=1440):raise ValueError('invalid_input')
    pace=body.get('pace')
    if pace not in (None,'quick','standard','deep'):raise ValueError('invalid_input')
    proposal=TripUtteranceProposal([TripActionProposal(kind,target_mentions=names('targets'),
        secondary_target_mentions=names('references'),preference_tags=tags,time_value_minutes=minutes,
        time_constraint_mode='hard' if kind=='SET_HARD_TIME_LIMIT' else 'soft' if kind=='SET_TIME_TARGET' else None,
        pace=pace,explicit_replan=kind=='FULL_REPLAN',requested_count=body.get('count'),reduction_goal=body.get('goal'))])
    proposal=normalize_actions(proposal)
    service=ConversationalTripService(app.store,app.repo,None,trip_service=app.trips,coordinator=app.replans)
    service.actions.parser=ExplicitControlParser(proposal)
    return service.handle_turn(trip.trip_id,'Explicit web control').to_dict()

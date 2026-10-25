"""Thin local web adapter. Frozen planning/world services remain the authority."""
import copy
import json
from pathlib import Path
import os
import secrets
import threading
import time
from .poi_repository import POIRepository
from .route_entry import RouteEntryService
from .intent_models import RouteIntent, RouteMode
from .trip_state import TripState, TripStateDelta
from .trip_store import InMemoryTripStore, TripService
from .trip_replanning import ReplanningCoordinator, ReplanReason
from .services.world_context_service import WorldContextService
from .services.walking_route_service import WalkingRouteService
from .providers.amap import AmapClient, AmapWalkingProvider
from .llm_client import DeepSeekLLMClient
from .trip_conversation import ConversationalTripService, InMemoryTripConversationStore
from .web_trip_actions import execute_control
from .web_english import EnglishPlaceLabels
from .web_arrival import WebArrival
from .map_guidance import MapGuidance, direction_lock


class WebApplication:
    def __init__(self, *, repository=None, entry=None, world=None):
        self.repo = repository or POIRepository()
        client = AmapClient()
        self.world = world or WorldContextService.from_environment(repository=self.repo,client=client)
        self.entry = entry or RouteEntryService(self.repo,
            llm_client=DeepSeekLLMClient() if os.environ.get('DEEPSEEK_API_KEY') else None,
            walking_service=WalkingRouteService(AmapWalkingProvider(client)))
        self.store = InMemoryTripStore()
        self.trips = TripService(self.store)
        self.replans = ReplanningCoordinator(self.store,self.repo,walking_service=self.entry.walking_service)
        self.conversations=InMemoryTripConversationStore()
        self.llm=DeepSeekLLMClient() if os.environ.get("DEEPSEEK_API_KEY") else None
        self.english=EnglishPlaceLabels(self.llm)
        self.arrivals=WebArrival(self)
        self.guidance=MapGuidance(client,self.entry.walking_service,labels=self.english)
        self.sessions = {}
        self.lock = threading.RLock()
        raw = {p['id']:p for p in self.repo.get_raw_data()['pois']}
        self.catalogue = []
        english=json.loads((Path(__file__).resolve().parents[1]/"frontend/catalogue-en.json").read_text(encoding="utf-8"))
        for p in self.repo.get_all_pois():
            row = raw[p.id]
            self.catalogue.append(dict(id=p.id,name_en=english["names"].get(p.id,p.name_en),name_zh=p.name_zh,
                coordinates=p.coordinates,zone_id=p.zone_id,zone_en=p.zone_name_en,zone_zh=p.zone_name_zh,
                category={**row.get('category',{}),'en':row.get('category',{}).get('en','Place').replace('_',' ').title()},summary={**row.get('content',{}),'summary_en':english['summaries'].get(p.id,'')},
                interest_tags=p.interest_tags,visit_modes=p.visit_profile.supported_modes,
                environment=p.environment))

    def session(self, token=None):
        with self.lock:
            now=time.monotonic()
            for key,value in list(self.sessions.items()):
                if now-value['touched']>86400:
                    if value['trip_id']:self.store.delete(value['trip_id'])
                    del self.sessions[key]
            if token not in self.sessions:
                if len(self.sessions)>=256:raise ValueError('session_capacity')
                token=secrets.token_urlsafe(32)
                self.sessions[token]=dict(trip_id=None,pending=None,touched=now,lock=threading.RLock())
            self.sessions[token]['touched']=now
            return token,self.sessions[token]

    def bootstrap(self, session):
        return dict(pois=copy.deepcopy(self.catalogue),zones=self.repo.get_raw_data()['metadata']['walk_zones'],
            taxonomy=self.repo.taxonomy,trip=self.current_trip(session),
            capabilities=dict(natural_language=self.entry.parser is not None,
                              live_world=bool(os.environ.get('AMAP_WEB_SERVICE_KEY')),
                              nearby_add_stop=False,english_map=bool(os.environ.get('AMAP_JS_API_KEY')),map_js_key=os.environ.get('AMAP_JS_API_KEY','')),pending=bool(session['pending']))

    def current_trip(self, session):
        if not session['trip_id']:return None
        result=self.trips.get_trip(session['trip_id']).to_dict()
        result['direction_lock']=direction_lock(result['active_route'])
        if session.get('change_history'):result['change_history']=copy.deepcopy(session['change_history'])
        return result

    def _result(self, session, result):
        session['pending']=result if result.status in ('needs_clarification','needs_route_quality_clarification') else None
        ended=None
        if result.status=='success':
            current=self.current_trip(session)
            if current and current['status']=='ACTIVE':
                authorization=session.get('replacement')
                if authorization!=(current['trip_id'],current['state_revision']):raise ValueError('stale_state_conflict')
            trip=TripState.create(result.route_plan,result.intent)
            self.store.create(trip)
            if current and current['status']=='ACTIVE':
                try:ended=self.trips.abandon_trip(current['trip_id'],expected_revision=current['state_revision']).to_dict()
                except Exception:
                    self.store.delete(trip.trip_id)
                    raise
            old=session['trip_id'];session['trip_id']=trip.trip_id
            session['change_history']=[]
            if old:self.store.delete(old)
        if session['pending'] is None:session.pop('replacement',None)
        return dict(entry=result.to_dict(),trip=self.current_trip(session),ended_trip=ended)

    def generate(self, session, body):
        with session['lock']:
            session.pop('replacement',None)
            session['pending']=None
            current=self.current_trip(session)
            if current and current['status']=='ACTIVE':
                if body.get('replace_active') is not True:raise ValueError('active_trip_requires_replan')
                if body.get('expected_trip_id')!=current['trip_id'] or type(body.get('expected_revision')) is not int or body['expected_revision']!=current['state_revision']:
                    raise ValueError('stale_state_conflict')
                session['replacement']=(current['trip_id'],current['state_revision'])
            text=body.get('text','')
            if not isinstance(text,str) or len(text)>2000:raise ValueError('invalid_input')
            if text.strip():
                if self.entry.parser is None:raise ValueError('natural_language_unavailable')
                form=body.get('intent')
                if form is None:
                    intent=self.entry.parse_plan(text)
                else:
                    allowed={'route_mode','available_minutes','interest_tags','culture_tags','experience_tags','travel_pace','must_go_poi_ids','preferred_zone'}
                    if not isinstance(form,dict) or set(form)-allowed:raise ValueError('invalid_input')
                    selected=self.entry.clarification.prepare(RouteIntent.from_dict(form))
                    if selected.route_mode!=RouteMode.PLAN_FOR_ME:raise ValueError('invalid_input')
                    prompt=('Plan using these existing form selections as defaults. The additional user request supplements them; '
                            'only replace a selected field if the user explicitly changes it. Retain selected time and interests '
                            'when the additional request only adds a place. A required place takes priority over the default '
                            'neighbourhood; keep the route within its zone. Do not ask again for supplied fields.\n'
                            'Selected form: '+json.dumps(form,ensure_ascii=False)+'\nAdditional user request: '+text)
                    intent=self.entry.parse_plan(prompt)
                    intent.route_mode=RouteMode.PLAN_FOR_ME
                    if intent.available_minutes is None:intent.available_minutes=selected.available_minutes
                    for field in ('interest_tags','culture_tags','experience_tags'):
                        if not getattr(intent,field):setattr(intent,field,[v for v in getattr(selected,field) if v not in intent.avoid_tags])
                    intent.must_go_poi_ids=list(dict.fromkeys([*selected.must_go_poi_ids,*intent.must_go_poi_ids]))
                    if intent.preferred_zone is None:intent.preferred_zone=selected.preferred_zone
                    required_zones={self.repo.get_poi_by_id(pid).zone_id for pid in intent.must_go_poi_ids}
                    if len(required_zones)==1:intent.preferred_zone=next(iter(required_zones))
                    intent=self.entry.clarification.prepare(intent)
            else:
                allowed={'route_mode','available_minutes','interest_tags','culture_tags','experience_tags','travel_pace',
                         'must_go_poi_ids','preferred_zone','start_poi_id','start_lat','start_lng','start_coordinate_system','surprise_seed'}
                payload=body.get('intent',{})
                if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('invalid_input')
                intent=RouteIntent.from_dict(payload)
            self._validate_zone(intent)
            return self._result(session,self.entry.generate(intent))

    def clarify(self, session, body):
        with session['lock']:
            result=session['pending']
            if result is None:raise ValueError('no_pending_question')
            if result.status=='needs_route_quality_clarification':
                return self._result(session,self.entry.answer_route_quality_clarification(result,body['answer']))
            intent=self.entry.clarification.answer(result.intent,body.get('answers',{}))
            return self._result(session,self.entry.generate(intent))

    def action(self, session, body):
        with session['lock']:
            trip=self.current_trip(session)
            if not trip:raise ValueError('no_trip')
            revision=body.get('revision')
            if type(revision) is not int or revision!=trip['state_revision']:raise ValueError('stale_state_conflict')
            action=body.get('action')
            if action=='replan':
                fields=body.get('delta',{})
                if not isinstance(fields,dict) or set(fields)-{'remaining_minutes','pace','add_interest_tags','remove_interest_tags','add_must_go_poi_ids'}:
                    raise ValueError('invalid_input')
                result=self.replans.replan(session['trip_id'],TripStateDelta(**fields,request_replan=True),
                                               primary_reason=ReplanReason.MANUAL,expected_revision=revision)
                status='success_replanned' if result.committed else 'no_change' if result.status=='no_change' else 'replan_failed'
                turn=dict(status=status,replan_result=result.to_dict(),error_code=None if result.committed else result.status)
                self._feedback(session,trip,turn,'FULL_REPLAN')
                return dict(trip=self.current_trip(session),replan=result.to_dict(),turn=turn)
            methods={'start':'start_trip','complete':'complete_stop','skip':'skip_stop','abandon':'abandon_trip'}
            if action not in methods:raise ValueError('invalid_action')
            method=getattr(self.trips,methods[action])
            args=[session['trip_id']]+([body.get('poi_id')] if action in ('complete','skip') else [])
            result=method(*args,expected_revision=revision)
            turn=None
            if action=='skip':
                turn=dict(status='success_core_action')
                self._feedback(session,trip,turn,'SKIP_PLACE')
            return dict(trip=self.current_trip(session),turn=turn)

    def reality(self, session, body):
        trip=self.current_trip(session)
        if not trip:raise ValueError('no_trip')
        return self.world.check_route_reality(trip,trip['route_versions'][-1],body.get('current_location')).to_dict()

    def nearby(self, body):
        result=self.world.search_nearby_services(core_poi_id=body.get('poi_id'),
            current_location=body.get('current_location'),categories=body.get('categories'),radius_m=800,limit_per_category=5).to_dict()
        return self.english.apply(result) if body.get('lang')=='en' else result

    def guidance_direction(self, session, body):
        with session['lock']:
            trip=self.store.get(session['trip_id'])
            revision=body.get('revision')
            if type(revision) is not int or revision!=trip.state_revision:raise ValueError('stale_state_conflict')
            if body.get('direction') not in ('original','reverse'):raise ValueError('invalid_input')
            if trip.status!='PLANNED' or direction_lock(trip.active_route):raise ValueError('direction_locked')
            desired=[s['poi_id'] for s in trip.original_route['ordered_pois']]
            if body['direction']=='reverse':desired.reverse()
            route=trip.active_route
            if desired==[s['poi_id'] for s in route['ordered_pois']]:return dict(trip=self.current_trip(session))
            if desired!=[s['poi_id'] for s in reversed(route['ordered_pois'])]:raise ValueError('direction_locked')
            from .route_engine import RouteEngine
            engine=RouteEngine(self.repo)
            route['ordered_pois'].reverse()
            total=0
            for i,stop in enumerate(route['ordered_pois']):
                km=engine._distance(route['ordered_pois'][i-1]['estimated_coordinates'],stop['estimated_coordinates']) if i else 0
                mins=km*1000/engine.speed
                stop.update(estimated_distance_from_previous_stop_km=km,estimated_distance_from_previous=km,
                            estimated_walking_minutes=mins,estimated_walking_minutes_from_previous=mins)
                total+=km
            route.update(total_estimated_distance_km=total,total_estimated_walking_minutes=total*1000/engine.speed)
            route['total_estimated_minutes']=route['total_stay_minutes']+route['total_estimated_walking_minutes']+(route.get('buffer_minutes') or 0)
            route['remaining_minutes']=route['request']['available_minutes']-route['total_estimated_minutes']
            route=self.entry.walking_service.hydrate_dict(route)
            trip.set_walk_direction(route)
            self.store.save_if_revision(trip,revision)
            return dict(trip=self.current_trip(session))

    def _validate_zone(self, intent):
        zones={self.repo.get_poi_by_id(pid).zone_id for pid in intent.must_go_poi_ids}
        if len(zones)>1 or (zones and intent.preferred_zone and intent.preferred_zone not in zones):
            raise ValueError('zone_mismatch')

    def turn(self, session, body):
        with session['lock']:
            trip=self.current_trip(session)
            if not trip:raise ValueError('no_trip')
            if type(body.get('revision')) is not int or body['revision']!=trip['state_revision']:raise ValueError('stale_state_conflict')
            if body.get('kind'):
                result=execute_control(self,session,body)
                self.conversations.clear(session['trip_id'])
            else:
                text=body.get('text')
                if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('invalid_input')
                if self.llm is None:raise ValueError('natural_language_unavailable')
                service=ConversationalTripService(self.store,self.repo,self.llm,trip_service=self.trips,
                    coordinator=self.replans,conversation_store=self.conversations)
                result=service.handle_turn(session['trip_id'],text).to_dict()
            self._feedback(session,trip,result,body.get('text') or body.get('kind',''))
            # Diagnostics/provider prompts stay server-side; the UI receives user-facing results only.
            result.pop('nlu_trace',None);result.pop('parsed_command',None)
            return dict(trip=self.current_trip(session),turn=result)

    def _feedback(self, session, before, result, request_text):
        from .web_route_feedback import change_summary
        feedback=change_summary(before,self.current_trip(session),result,self.repo,request_text)
        result['change_summary']=feedback
        session.setdefault('change_history',[]).append(copy.deepcopy(feedback))

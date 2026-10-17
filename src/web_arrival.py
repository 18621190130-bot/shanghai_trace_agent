"""Arrival presentation adapter. No domain mutations; ProximityService is authoritative."""
import json
import math
import os
from pathlib import Path
import time
from .providers.amap import AmapClient
from .providers.amap.arrival import AmapArrivalProvider,entrance_coordinate
from .providers.base import ExternalProviderError

DATA=Path(__file__).resolve().parents[1]/'data'
def remaining_target(trip):
    done=set(trip['visited_poi_ids']+trip['skipped_poi_ids'])
    return next((s for s in trip['active_route']['ordered_pois'] if s['poi_id'] not in done),None)
def quality(position,now=None):
    if not isinstance(position,dict):return False
    now=time.time()*1000 if now is None else now
    vals=[position.get(k) for k in ('latitude','longitude','timestamp','accuracy')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in vals):return False
    lat,lng,stamp,accuracy=vals
    return -90<=lat<=90 and -180<=lng<=180 and 0<=accuracy<=50 and -5000<=now-stamp<=30000 and position.get('coordinate_system') in ('WGS84','GCJ02')

class WebArrival:
    def __init__(self,app,provider=None,clock=time.time):
        self.app=app;self.clock=clock;self.provider=provider or AmapArrivalProvider(AmapClient())
        self.mappings=json.loads((DATA/'amap_poi_mappings.json').read_text(encoding='utf-8'))
        self.cache={}
        path=DATA/'poi_arrival_locations.json'
        if path.exists():self.cache=json.loads(path.read_text(encoding='utf-8')).get('records',{})
    @property
    def demo_enabled(self):return os.environ.get('TRACEMATE_ENABLE_DEMO_MODE','').lower() in ('true','1')
    def context(self,session):
        trip=self.app.current_trip(session);cfg=self.app.world.proximity.config
        target=remaining_target(trip) if trip else None
        poi=self.app.repo.get_poi_by_id(target['poi_id']) if target else None
        return dict(trip_id=trip['trip_id'] if trip else None,revision=trip['state_revision'] if trip else None,active=bool(trip and trip['status']=='ACTIVE'),target=target,target_location=dict(lat=poi.coordinates[0],lng=poi.coordinates[1],coordinate_system='GCJ02') if poi else None,arrival_threshold_m=cfg.arrival_threshold_m,near_threshold_m=cfg.near_threshold_m,demo_enabled=self.demo_enabled)
    def check(self,session,body):
        with session['lock']:
            ctx=self.context(session)
            if not ctx['active'] or not ctx['target']:return dict(status='INACTIVE',context=ctx)
            if body.get('trip_id')!=ctx['trip_id'] or body.get('revision')!=ctx['revision'] or body.get('poi_id')!=ctx['target']['poi_id']:raise ValueError('stale_state_conflict')
            source=body.get('source');position=body.get('position')
            if source=='MANUAL':return dict(status='ARRIVED',arrival_source='MANUAL',context=ctx,position=None)
            if source not in ('GPS','DEMO') or (source=='DEMO' and not self.demo_enabled):raise ValueError('invalid_input')
            if not quality(position,self.clock()*1000):return dict(status='LOW_QUALITY',arrival_source=source,context=ctx,position=None)
            if position.get('source')!=source:raise ValueError('invalid_input')
            if source=='GPS' and position['coordinate_system']!='WGS84':raise ValueError('invalid_input')
            if source=='DEMO' and position['coordinate_system']!='GCJ02':raise ValueError('invalid_input')
            current=dict(lat=position['latitude'],lng=position['longitude'],coordinate_system=position['coordinate_system'])
            result=self.app.world.check_arrival(current,ctx['target']['poi_id']).to_dict()
            return dict(status=result['status'],arrival_source=source,context=ctx,proximity=result,position=position)
    def content(self,poi_id):
        poi=self.app.repo.get_poi_by_id(poi_id)
        if poi is None:raise ValueError('invalid_input')
        profile=self.app.repo.get_spatial_profile(poi_id) or {};kind=profile.get('spatial_type','POINT');m=self.mappings.get(poi_id,{})
        identity=m.get('amap_poi_id') if m.get('identity_mapping_status')=='MATCHED' else None
        target=poi.coordinates;cached=self.cache.get(poi_id)
        if kind=='POINT' and identity and cached is None:
            try:cached=dict(provider_id=identity,navi=self.provider.fetch([identity]).get(identity,{}).get('navi',{}),retrieved_at=self.clock())
            except ExternalProviderError:cached=dict(provider_id=identity,navi={},unavailable=True,retrieved_at=self.clock())
            self.cache[poi_id]=cached
        coord=entrance_coordinate((cached or {}).get('navi'),target) if identity and (cached or {}).get('provider_id')==identity and kind=='POINT' else None
        raw=json.loads((DATA/'poi_arrival_content.json').read_text(encoding='utf-8')).get('records',{}).get(poi_id,{})
        location=dict(location_type='UNAVAILABLE',source_type='UNAVAILABLE',arrival_location=None,source='UNAVAILABLE',verification='UNAVAILABLE',display_note='entranceUnavailable')
        if coord:location.update(location_type='AMAP_PROVIDER_ENTRANCE',source_type='AMAP_PROVIDER_ENTRANCE',arrival_location=coord,source='AMAP_PROVIDER_ENTRANCE',verification='PROVIDER_REPORTED',display_note='providerEntrance',retrieved_at=cached.get('retrieved_at'))
        else:
            reviewed=raw.get('arrival_point') or {}
            point=reviewed.get('location') or {}
            valid=reviewed.get('reviewed') is True and point.get('coordinate_system')=='GCJ02' and all(type(point.get(k)) in (float,int) and math.isfinite(point[k]) for k in ('lat','lng')) and 30<=point['lat']<=32 and 120<=point['lng']<=123
            if valid:location.update(location_type='TRACE_REVIEWED_ARRIVAL_POINT',source_type='TRACE_REVIEWED_ARRIVAL_POINT',source='TRACE_REVIEWED_ARRIVAL_POINT',arrival_location={k:point[k] for k in ('lat','lng','coordinate_system')},verification='MANUALLY_REVIEWED',display_note='suggestedStart' if kind!='POINT' else 'suggestedArrival')
            elif target:location.update(suggested_location=dict(lat=target[0],lng=target[1],coordinate_system='GCJ02'),verification='ROUTE_POINT_NOT_ENTRANCE_VERIFIED',display_note='suggestedStart' if kind!='POINT' else 'suggestedArrival')
        image=raw.get('entrance_image') or {}
        image=image if isinstance(image,dict) and (image.get('reviewed') is True or image.get('source')=='CURATED') else None
        hooks=raw.get('arrival_hook') or {};notice=raw.get('what_to_notice') or {}
        hooks={lang:hooks.get(lang) if isinstance(hooks.get(lang),str) else None for lang in ('en','zh')} if isinstance(hooks,dict) else {}
        notice={lang:[v for v in notice.get(lang,[]) if isinstance(v,str) and v.strip()] if isinstance(notice.get(lang),list) else [] for lang in ('en','zh')} if isinstance(notice,dict) else {}
        return dict(poi_id=poi_id,route_role=poi.route_role_primary,spatial_type=kind,location=location,entrance_image=image,arrival_hook=hooks,what_to_notice=notice,content_status=raw.get('content_status','PENDING'))

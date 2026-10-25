import {request} from './api.js';
import {escapeHTML as e,remaining,hasCJK} from './lib.js';
import {button} from './components.js';
import {HeadingTracker,movementHeading} from './location-heading.js';

export function recommendDirection(original,reverse){
 if(original?.availability!=='AVAILABLE'||reverse?.availability!=='AVAILABLE')return {direction:'original',reason:'comparisonUnavailable',saved:0};
 const saved=original.duration_s-reverse.duration_s;
 return saved>=180&&saved>=original.duration_s*.15?{direction:'reverse',reason:'reverseSuggested',saved}:{direction:'original',reason:'originalSuggested',saved:0};
}
export class NavigationController {
 constructor(host){Object.assign(this,host);this.epoch=0;this.searchEpoch=0;this.baseline='walking';this.headingTracker=new HeadingTracker(value=>{this.deviceHeading=value;this.refreshMap();});}
 sync(){const stamp=this.state.userLocation?.timestamp;if(stamp!==this.locationStamp){this.locationStamp=stamp;clearTimeout(this.locationExpiry);if(stamp)this.locationExpiry=setTimeout(()=>this.refreshMap(),Math.max(0,31000-(Date.now()-stamp)));}const trip=this.state.trip,key=trip?`${trip.trip_id}:${trip.state_revision}`:null;
  if(key!==this.key){this.key=key;this.epoch++;this.searchEpoch++;this.busy=false;this.searchBusy=false;this.guidance=null;this.options=[];this.comparison=null;this.error=null;this.pickPoint=false;if(trip?.trip_id!==this.tripId){this.state.userLocation=null;this.origin=null;this.searchResults=[];this.open=false;this.tripId=trip?.trip_id;}if(trip?.status!=='PLANNED')this.open=false;}
  if(this.state.screen!=='route'||!['PLANNED','ACTIVE'].includes(trip?.status)){clearTimeout(this.locationExpiry);this.locationStamp=null;this.headingTracker.stop();this.deviceHeading=null;this.pickPoint=false;this.open=false;this.guidance=null;this.epoch++;this.busy=false;}
 }
 heading(){const p=this.state.userLocation;if(!p||!p.timestamp||Date.now()-p.timestamp>30000)return null;return this.deviceHeading&&Date.now()-this.deviceHeading.timestamp<5000?this.deviceHeading.angle:p.heading??null;}
 point(id){const stop=this.state.trip?.active_route.ordered_pois.find(s=>s.poi_id===id),p=this.getPoi(id),c=stop?.estimated_coordinates||p?.coordinates;return c?{lat:c[0],lng:c[1],coordinate_system:'GCJ02'}:null;}
 route(origin,destination,mode){return request('/api/guidance/route',{origin,destination,mode}).catch(()=>({mode,availability:'UNAVAILABLE',segments:[]}));}
 async setOrigin(point){this.epoch++;this.state.mobileView='itinerary';this.origin=point;this.searchResults=[];this.pickPoint=false;this.guidance=null;this.options=[];this.comparison=null;await this.compare();}
 async compare(){if(!this.origin)return;const token=++this.epoch;this.busy=true;this.error=null;this.render();const trip=this.state.trip,stops=trip.original_route.ordered_pois;
  if(trip.direction_lock)this.comparison={direction:'original',reason:'direction_locked',saved:0};
  else{const [a,b]=await Promise.all([this.route(this.origin,this.point(stops[0].poi_id),this.baseline),this.route(this.origin,this.point(stops.at(-1).poi_id),this.baseline)]);if(token!==this.epoch)return;this.comparison=recommendDirection(a,b);}
  await this.loadOptions(token);
 }
 async loadOptions(token=++this.epoch){this.busy=true;this.render();const destination=this.point(this.state.trip.active_route.ordered_pois[0].poi_id);
  const results=await Promise.all(['walking','transit','taxi','bicycle'].map(mode=>this.route(this.origin,destination,mode)));if(token!==this.epoch)return;
  this.options=results.sort((a,b)=>(a.availability==='AVAILABLE'?a.duration_s:Infinity)-(b.availability==='AVAILABLE'?b.duration_s:Infinity));this.busy=false;
  const first=this.options.find(r=>r.availability==='AVAILABLE');this.guidance=first?{...first,kind:'start_access'}:null;if(!first)this.error='guidanceUnavailable';this.render();
 }
 async gps(){if(!navigator.geolocation){this.error='gpsUnavailable';this.render();return;}const token=++this.epoch;this.busy=true;this.render();
  navigator.geolocation.getCurrentPosition(async p=>{if(token!==this.epoch)return;if(p.coords.accuracy>50||Date.now()-p.timestamp>30000){this.busy=false;this.error='gpsLowQuality';this.render();return;}
   try{const result=await request('/api/guidance/location',{location:{lat:p.coords.latitude,lng:p.coords.longitude,coordinate_system:'WGS84'}});if(token!==this.epoch)return;this.state.userLocation={...result.location,accuracy:p.coords.accuracy,timestamp:p.timestamp,heading:movementHeading(p.coords)};await this.setOrigin(result.location);}catch(error){if(token!==this.epoch)return;this.busy=false;this.error=error.code==='location_outside'?'locationOutside':'guidanceUnavailable';this.render();}
  },err=>{if(token!==this.epoch)return;this.busy=false;this.error=err.code===1?'gpsDenied':err.code===3?'gpsTimeout':'gpsUnavailable';this.render();},{enableHighAccuracy:true,maximumAge:0,timeout:12000});
 }
 async search(){const query=document.querySelector('#origin-query')?.value?.trim();if(!query)return;const token=++this.searchEpoch;this.query=query;this.searchBusy=true;this.error=null;this.render();try{const r=await request('/api/guidance/search',{query});if(token!==this.searchEpoch)return;this.searchResults=r.results;if(!r.results.length)this.error='noOriginResults';}catch{if(token!==this.searchEpoch)return;this.error='guidanceUnavailable';}this.searchBusy=false;this.render();}
 async directions(id){if(!['PLANNED','ACTIVE'].includes(this.state.trip?.status)){this.state.error='planForGuidance';this.render();return;}const service=this.state.nearby?.results.find(p=>p.service_poi_id===id);if(!service?.location){this.error='noServiceLocation';this.render();return;}
  const p=this.state.userLocation,valid=p&&p.timestamp&&Date.now()-p.timestamp<=30000&&p.accuracy<=50;
  const origin=valid?p:this.origin||this.point(this.state.nearbyOrigin||this.state.selected||remaining(this.state.trip||{})[0]?.poi_id);
  if(!origin){this.error='noGuidanceOrigin';this.render();return;}
  this.returnTarget=this.point(remaining(this.state.trip||{})[0]?.poi_id)||origin;this.returnOrigin=service.location;this.originSource=valid?'nearbyGpsOrigin':this.origin?'manualOrigin':'nearbyAnchorOrigin';
  this.open=false;this.pickPoint=false;this.arrivals.openId=null;this.state.detail=null;this.state.mobileView='map';this.state.screen='route';if(location.hash!=='#route')location.hash='route';await this.detour(origin,service.location,'nearby_detour');
 }
 async detour(origin,destination,kind){const token=++this.epoch;this.guidance=null;this.busy=true;this.error=null;this.render();const result=await this.route(origin,destination,'walking');if(token!==this.epoch)return;this.busy=false;if(result.availability==='AVAILABLE')this.guidance={...result,kind};else this.error='guidanceUnavailable';this.render();}
 async action(action,value){switch(action){
  case 'nav-open':this.open=true;this.error=null;this.render();return;
  case 'nav-close':this.epoch++;this.searchEpoch++;this.open=false;this.busy=false;this.searchBusy=false;this.pickPoint=false;this.guidance=null;this.render();this.fit();return;
  case 'nav-gps':return this.gps();
  case 'nav-search':return this.search();
  case 'nav-search-result':{const p=this.searchResults?.[Number(value)];if(p)return this.setOrigin(p.location);return;}
  case 'nav-pick':this.searchEpoch++;this.epoch++;this.busy=false;this.pickPoint=!this.pickPoint;this.state.mobileView='map';this.render();return;
  case 'nav-baseline':this.baseline=value;return this.compare();
  case 'nav-direction':{if(this.busy||this.state.trip.direction_lock)return;const token=++this.epoch;this.busy=true;this.guidance=null;this.render();try{const r=await request('/api/guidance/direction',{revision:this.state.trip.state_revision,direction:value});if(this.state.trip.trip_id!==r.trip.trip_id)return;this.state.trip=r.trip;if(token!==this.epoch){this.sync();this.render();return;}this.key=`${r.trip.trip_id}:${r.trip.state_revision}`;this.state.realityKey=null;await this.loadOptions(token);this.refreshReality();}catch(error){if(token!==this.epoch)return;this.busy=false;this.error=error.code||'guidanceUnavailable';this.render();}return;}
  case 'nav-mode':{const r=this.options?.find(r=>r.mode===value&&r.availability==='AVAILABLE');if(r){this.guidance={...r,kind:'start_access'};this.state.mobileView='map';this.render();}return;}
  case 'nav-directions':return this.directions(value);
  case 'nav-back':this.epoch++;this.busy=false;this.guidance=null;this.error=null;this.render();this.fit();return;
  case 'nav-return':{const p=this.state.userLocation,origin=p?.timestamp&&Date.now()-p.timestamp<30000&&p.accuracy<=50?p:this.returnOrigin;this.originSource=origin===p?'nearbyGpsOrigin':'serviceReturnOrigin';if(origin&&this.returnTarget)return this.detour(origin,this.returnTarget,'return_to_route');return;}
  case 'nav-heading':if(!await this.headingTracker.enable())this.error='headingUnavailable';this.render();return;
 }}
 metrics(r){return `${Math.ceil(r.duration_s/60)} ${this.t('minutesShort')}${Number.isFinite(r.distance_m)?` · ${this.distance(r.distance_m)}`:''}`;}
 panel(){const t=this.t;if(!this.open||this.state.trip?.status!=='PLANNED')return '';const original=this.state.trip.original_route.ordered_pois[0].poi_id,current=this.state.trip.active_route.ordered_pois[0].poi_id;
  return `<section class="smart-start"><div class="section-heading"><h2>Smart Start</h2>${button(t('close'),'nav-close','text')}</div><h3>${e(t('yourStartingPoint'))}</h3><p>${e(t('startOptional'))}</p><div class="guidance-actions">${button(t('useGps'),'nav-gps','secondary')}${button(t('pickOnMap'),'nav-pick','secondary')}</div>${this.origin?`<p>${e(t('manualOrigin'))}: ${this.origin.lng.toFixed(5)}, ${this.origin.lat.toFixed(5)}</p>`:''}<form id="origin-search"><label class="field-label">${e(t('searchOrigin'))}<input id="origin-query" value="${e(this.query||'')}" maxlength="100"></label><button class="button secondary" ${this.searchBusy?'disabled':''}>${e(t('search'))}</button></form><div class="origin-results">${(this.searchResults||[]).map((r,i)=>button(this.state.lang==='en'&&hasCJK(r.name)?`${this.query} · ${i+1} (${r.location.lng.toFixed(4)}, ${r.location.lat.toFixed(4)})`:r.name,'nav-search-result','text',`data-value="${i}"`)).join('')}</div>
  ${this.origin?`<h3>${e(t('walkDirection'))}</h3><p>${e(t('comparisonBasis'))}</p><div class="guidance-actions">${['walking','transit'].map(m=>button(t('mode_'+m),'nav-baseline',this.baseline===m?'primary':'secondary',`data-value="${m}" ${this.busy?'disabled':''}`)).join('')}</div>${this.comparison?`<p role="status">${e(t(this.comparison.reason))}${this.comparison.saved?` · ${Math.round(this.comparison.saved/60)} ${e(t('minutesSaved'))}`:''}</p>`:''}<div class="guidance-actions">${button(t('keepOriginal'),'nav-direction',current===original?'primary':'secondary',`data-value="original" ${this.busy||this.state.trip.direction_lock?'disabled':''}`)}${button(t('reverseWalk'),'nav-direction',current!==original?'primary':'secondary',`data-value="reverse" ${this.busy||this.state.trip.direction_lock?'disabled':''}`)}</div><h3>${e(t('gettingThere'))}</h3><p>${e(this.name(current))}</p><div class="transport-options">${(this.options||[]).map(r=>`<button data-action="nav-mode" data-value="${r.mode}" class="transport-option ${this.guidance?.mode===r.mode?'selected':''}" ${r.availability!=='AVAILABLE'||this.busy?'disabled':''}><strong>${e(t('mode_'+r.mode))}</strong><span>${r.availability==='AVAILABLE'?e(this.metrics(r)):e(t('guidanceUnavailable'))}</span></button>`).join('')}</div><p class="guidance-note">${e(t('transportCaveat'))}</p>`:''}${this.busy?`<p role="status">${e(t('guidanceLoading'))}</p>`:''}${this.error?`<p role="alert">${e(t(this.error))}</p>`:''}${button(t('startWalk'),'start','primary',this.busy?'disabled':'')}</section>`;
 }
 mapPanel(){const r=this.guidance,t=this.t;return `<div class="map-guidance-ui">${this.pickPoint?`<p role="status">${e(t('pickOnMapHint'))}</p>${button(t('cancel'),'nav-pick','secondary')}`:''}${r&&r.kind!=='start_access'?`<strong>${e(t(r.kind==='return_to_route'?'returnToRoute':'nearbyDetour'))}</strong><p>${e(this.metrics(r))} · ${e(t(this.originSource||'nearbyAnchorOrigin'))}</p>${button(t('backToWalk'),'nav-back','secondary')}${r.kind==='nearby_detour'?button(t('returnToRoute'),'nav-return','secondary'):''}`:''}${this.busy&&!this.open?`<p role="status">${e(t('guidanceLoading'))}</p>`:''}${this.error&&!this.open?`<p role="alert">${e(t(this.error))}</p>`:''}${this.state.userLocation?button(t('enableHeading'),'nav-heading','text'):''}</div>`;}
}

import {request} from './api.js';
import {BrowserLocationProvider} from './arrival-session.js';
import {escapeHTML as e} from './lib.js';
import {button} from './components.js';

export function distanceTo(a,b){if(!a||!b)return Infinity;const rad=Math.PI/180,dlat=(b.lat-a.lat)*rad,dlng=(b.lng-a.lng)*rad;const h=Math.sin(dlat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dlng/2)**2;return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));}
export function startProximity(position,target,now=Date.now()){
 if(!position||![position.lat,position.lng,position.accuracy,position.timestamp].every(Number.isFinite)||position.coordinate_system!=='GCJ02'||position.accuracy<0||position.accuracy>50||now-position.timestamp>30000||now-position.timestamp< -5000)return 'startNeedsLocation';
 return distanceTo(position,target)<=80?'readyToStart':'startNotThere';
}
// One location owner for planning and arrival; mode changes invalidate in-flight fixes.
export class WalkLocationController {
 constructor({state,navigation,arrivals,render,focus,t}){Object.assign(this,{state,navigation,arrivals,render,focus,t});this.browser=new BrowserLocationProvider();this.epoch=0;this.sequence=0;this.clickEpoch=0;this.demo=false;arrivals.externalLocation=true;}
 target(){return this.navigation.point(this.state.trip?.active_route.ordered_pois[0]?.poi_id);}
 status(){return startProximity(this.state.userLocation,this.target());}
 ready(){return this.status()==='readyToStart';}
 sync(){const trip=this.state.trip,enabled=this.state.screen==='route'&&['PLANNED','ACTIVE'].includes(trip?.status);
  if(!enabled){this.stop();this.entry=null;return;}
  if(this.entry!==trip.trip_id){this.stop();this.entry=trip.trip_id;if(globalThis.DeviceOrientationEvent&&!globalThis.DeviceOrientationEvent.requestPermission)this.navigation.headingTracker?.enable();this.demo=false;this.initialized=false;this.arrivals.mode='GPS';this.state.userLocation=null;if(trip.status==='PLANNED')this.navigation.open=true;}
  if(trip.status==='PLANNED')this.navigation.open=true;
  const ready=trip.status==='PLANNED'&&this.ready();if(ready&&!this.wasReady)queueMicrotask(()=>globalThis.document?.querySelector('.start-ready')?.scrollIntoView({block:'nearest'}));this.wasReady=ready;
  if(!this.demo&&!this.watching){this.watching=true;const token=this.epoch;queueMicrotask(()=>{if(token!==this.epoch||!this.watching)return;this.browser.start(p=>this.receive(p,token),error=>{if(token!==this.epoch)return;this.sequence++;this.arrivals.epoch++;this.error=error;this.state.userLocation=null;this.render();});});}
 }
 stop(){this.epoch++;this.sequence++;this.clickEpoch++;this.browser.stop();this.watching=false;clearInterval(this.demoTimer);clearTimeout(this.expiry);}
 retry(){if(this.demo){this.focus();return;}this.stop();this.error=null;this.initialized=false;this.render();}
 async receive(p,token=this.epoch){if(token!==this.epoch||this.demo!==(p.source==='DEMO'))return;
  if(![p.latitude,p.longitude,p.accuracy,p.timestamp].every(Number.isFinite)||p.accuracy<0||p.accuracy>5000||Date.now()-p.timestamp>30000||Date.now()-p.timestamp< -5000){this.sequence++;this.error='gpsLowQuality';this.state.userLocation=null;this.render();return;}
  const seq=++this.sequence;try{const loc=p.coordinate_system==='GCJ02'?{lat:p.latitude,lng:p.longitude,coordinate_system:'GCJ02'}:(await request('/api/guidance/location',{location:{lat:p.latitude,lng:p.longitude,coordinate_system:'WGS84'}})).location;
   if(token!==this.epoch||seq!==this.sequence)return;
   this.error=null;this.state.userLocation={...loc,accuracy:p.accuracy,timestamp:p.timestamp,heading:p.heading,source:p.source};
   clearTimeout(this.expiry);this.expiry=setTimeout(()=>{if(token===this.epoch)this.render();},31000);
   if(this.state.trip.status==='ACTIVE'){this.render();if(p.accuracy<=50)await this.arrivals.observe(p);return;}
   if(!this.initialized){this.initialized=true;const n=this.navigation,stops=this.state.trip.original_route.ordered_pois,nearOriginal=startProximity(this.state.userLocation,n.point(stops[0].poi_id))==='readyToStart',nearReverse=!this.state.trip.direction_lock&&startProximity(this.state.userLocation,n.point(stops.at(-1).poi_id))==='readyToStart';
    if(nearOriginal||nearReverse){n.origin=loc;n.originLabel={kind:'gps'};const desired=nearOriginal?'original':'reverse',current=this.state.trip.active_route.ordered_pois[0].poi_id===stops[0].poi_id?'original':'reverse';if(desired!==current){n.busy=true;await n.applyDirection(desired,++n.epoch);}else this.render();}
    else if(!n.origin)await n.setOrigin(loc,{kind:'gps'});else this.render();
   }else this.render();
  }catch(err){if(token!==this.epoch||seq!==this.sequence)return;this.error=err.code==='location_outside'?'locationOutside':'gpsUnavailable';this.state.userLocation=null;this.render();}
 }
 toggleDemo(){if(!this.arrivals.context?.demo_enabled)return;this.stop();this.navigation.epoch++;this.navigation.busy=false;this.navigation.guidance=null;this.navigation.options=[];this.navigation.endpointOptions=null;this.demo=!this.demo;this.initialized=false;if(this.navigation.originLabel?.kind==='gps')this.navigation.origin=null;this.arrivals.epoch++;this.arrivals.mode=this.demo?'DEMO':'GPS';this.arrivals.position=null;this.state.userLocation=null;this.state.gps=null;this.error=null;this.render();}
 async click(point){if(!this.demo||!this.arrivals.context?.demo_enabled)return;clearInterval(this.demoTimer);const clickToken=++this.clickEpoch;this.initialized=false;const update=()=>this.receive({latitude:point.lat,longitude:point.lng,coordinate_system:'GCJ02',accuracy:1,timestamp:Date.now(),source:'DEMO'});await update();if(this.demo&&clickToken===this.clickEpoch&&this.state.screen==='route')this.demoTimer=setInterval(update,5000);}
 panel(){return `<div class="map-location-tools">${this.arrivals.context?.demo_enabled?button(this.t(this.demo?'demoExit':'demoEnter'),'nav-demo','secondary',`aria-pressed="${this.demo}"`):''}${this.demo?`<p role="status">${e(this.t('demoMapHint'))}</p>`:''}${this.error?`<p role="alert">${e(this.t(this.error))}</p>`:!this.state.userLocation?`<p role="status">${e(this.t('gpsWaiting'))}</p>`:''}</div>`;}
}

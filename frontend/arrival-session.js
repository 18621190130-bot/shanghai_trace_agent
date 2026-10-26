import {movementHeading} from './location-heading.js';
import {remaining} from './lib.js';
export class ArrivalHistory {
 constructor(storage){this.storage=storage;this.tripId=null;this.records=[];this.cycles={};this.members=[];}
 sync(trip){
  if(!trip)return;
  if(this.tripId!==trip.trip_id){this.tripId=trip.trip_id;let saved={};try{saved=JSON.parse(this.storage.getItem('tracemate-arrivals:'+this.tripId)||'{}');}catch{}this.records=Array.isArray(saved.records)?saved.records.filter(r=>r.trip_id===this.tripId):[];this.cycles=saved.cycles||{};this.members=saved.members||[];}
  const ids=trip.active_route.ordered_pois.map(s=>s.poi_id);
  for(const id of ids)if(!this.members.includes(id))this.cycles[id]=(this.cycles[id]||0)+1;
  this.members=ids;
  for(const r of this.records){r.visited_status=trip.visited_poi_ids.includes(r.core_poi_id);r.skipped_status=trip.skipped_poi_ids.includes(r.core_poi_id);}
  this.save();
 }
 save(){try{this.storage.setItem('tracemate-arrivals:'+this.tripId,JSON.stringify({records:this.records,cycles:this.cycles,members:this.members}));}catch{}}
 arrive(trip,source){this.sync(trip);const target=remaining(trip)[0];if(trip.status!=='ACTIVE'||!target)return null;const cycle=this.cycles[target.poi_id]||1;
  if(this.records.some(r=>r.core_poi_id===target.poi_id&&r.arrival_cycle===cycle))return null;
  const r={event_id:`${trip.trip_id}:${target.poi_id}:${cycle}`,trip_id:trip.trip_id,core_poi_id:target.poi_id,arrival_cycle:cycle,route_version_id_at_arrival:trip.route_versions.at(-1).version_id,arrival_source:source,arrived_at:new Date().toISOString(),dismissed_at:null,visited_status:false,skipped_status:false,stop:structuredClone(target),ordinal:trip.active_route.ordered_pois.findIndex(s=>s.poi_id===target.poi_id)+1,total:trip.active_route.ordered_pois.length};this.records.push(r);this.save();return r;
 }
 dismiss(id){const r=this.records.find(r=>r.event_id===id);if(r){r.dismissed_at=new Date().toISOString();this.save();}}
}
export function usablePosition(p,now=Date.now()){return !!p&&[p.latitude,p.longitude,p.timestamp,p.accuracy].every(Number.isFinite)&&p.accuracy>=0&&p.accuracy<=50&&now-p.timestamp>=-5000&&now-p.timestamp<=30000;}
export class BrowserLocationProvider {
 start(onPosition,onError){if(this.watch!==undefined)return;if(!globalThis.navigator?.geolocation){onError('gpsUnavailable');return;}try{this.watch=navigator.geolocation.watchPosition(p=>onPosition({latitude:p.coords.latitude,longitude:p.coords.longitude,coordinate_system:'WGS84',timestamp:p.timestamp,accuracy:p.coords.accuracy,heading:movementHeading(p.coords),source:'GPS'}),e=>onError(e.code===1?'gpsDenied':e.code===3?'gpsTimeout':'gpsUnavailable'),{enableHighAccuracy:true,maximumAge:0,timeout:12000});}catch{onError('gpsUnavailable');}}
 stop(){if(this.watch!==undefined)navigator.geolocation.clearWatch(this.watch);this.watch=undefined;}
}
export class DemoLocationProvider {
 position(context,stage){const offset=stage==='ARRIVED'?0:stage==='NEAR'?(context.arrival_threshold_m+context.near_threshold_m)/2:context.near_threshold_m+500;return {latitude:context.target_location.lat+offset/111195,longitude:context.target_location.lng,coordinate_system:'GCJ02',timestamp:Date.now(),accuracy:1,source:'DEMO'};}
}

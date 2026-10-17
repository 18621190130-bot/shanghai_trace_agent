export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const poiName = (poi,lang) => poi?.[lang==='zh'?'name_zh':'name_en'] || poi?.name || '';
export const minutes = (value,t) => Number.isFinite(value) ? `${Math.round(value)} ${t('min')}` : '—';
export const distance = (value,unit='km') => !Number.isFinite(value)?'—':`${(value/(unit==='mi'?1609.344:1000)).toFixed(value<(unit==='mi'?1609.344:1000)?2:1)} ${unit==='mi'?'mi':'km'}`;
export function walkingMetrics(route) {
  const live=route.walking_data_status==='AVAILABLE';
  return {live,metres:live?route.walking_distance_m:(route.planning_distance_m??route.total_estimated_distance_km*1000),
    walkingMinutes:live?route.walking_duration_s/60:route.total_estimated_walking_minutes,
    totalMinutes:live?route.walking_duration_s/60+(route.total_stay_minutes||0):route.total_estimated_minutes};
}
export const remaining = trip => (trip?.active_route?.ordered_pois||[]).filter(p=>![...(trip.visited_poi_ids||[]),...(trip.skipped_poi_ids||[])].includes(p.poi_id));
export function safeAsset(path) {return typeof path==='string' && /^\/assets\/[\w./-]+$/.test(path) && !path.includes('..') ? path : null;}
export function amapLink(point,name) {return `https://uri.amap.com/marker?position=${encodeURIComponent(`${point.lng},${point.lat}`)}&name=${encodeURIComponent(name)}&coordinate=gaode&callnative=0`;}
// AMap staticmap scale=1 uses a 512px world tile at each reported zoom.
// Calibrated against provider-drawn anchors, not the usual 256px tile convention.
export function project(lng,lat,zoom) {
  const scale=512*2**zoom, sin=Math.sin(Math.max(-85,Math.min(85,lat))*Math.PI/180);
  return [(lng+180)/360*scale,(.5-Math.log((1+sin)/(1-sin))/(4*Math.PI))*scale];
}
export function unproject(x,y,zoom) {const scale=512*2**zoom;return [x/scale*360-180,Math.atan(Math.sinh(Math.PI*(1-2*y/scale)))*180/Math.PI];}

export const hasCJK = value => /[\u3400-\u9fff]/u.test(String(value||''));
export function walkSummary(trip, explored=[]) {
 const visited=[...new Set(trip.visited_poi_ids)], skipped=[...new Set(trip.skipped_poi_ids)];
 const total=new Set([...visited,...skipped,...remaining(trip).map(p=>p.poi_id)]).size;
 const start=trip.event_history.find(e=>e.event_type==='trip_started'||e.kind==='trip_started');
 const end=[...trip.event_history].reverse().find(e=>['trip_completed','trip_abandoned'].includes(e.event_type||e.kind));
 const elapsed=start?Math.max(0,Math.floor((Date.parse(end?.timestamp||end?.at||trip.updated_at)-Date.parse(start.timestamp||start.at))/1000)):0;
 return {seconds:Number.isFinite(elapsed)?elapsed:0,visited:visited.length,total,rate:total?Math.round(visited.length/total*100):0,explored:[...new Set([...explored,...visited])]};
}

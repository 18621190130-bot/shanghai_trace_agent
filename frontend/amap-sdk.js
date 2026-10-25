import {MapLayers,routeStyle,auxiliaryStyle} from './map-layers.js';
import {escapeHTML as e,poiName} from './lib.js';
import {icon} from './components.js';
let sdkPromise;
function loadSDK(key){
 if(window.AMap)return Promise.resolve(window.AMap);
 if(!sdkPromise)sdkPromise=new Promise((resolve,reject)=>{
  window._AMapSecurityConfig={serviceHost:`${location.origin}/_AMapService`};
  const script=document.createElement('script');
  script.src=`https://webapi.amap.com/maps?v=1.4.15&key=${encodeURIComponent(key)}`;
  script.onload=()=>window.AMap?resolve(window.AMap):reject(Error('map_sdk_unavailable'));
  script.onerror=()=>reject(Error('map_sdk_unavailable'));document.head.append(script);
 }).catch(error=>{sdkPromise=null;throw error;});
 return sdkPromise;
}
export class SDKMapController {
 constructor(host,options){this.host=host;this.markers=new Map();Object.assign(this,options);this.viewport=options.viewport?.provider==='sdk'?options.viewport:null;
  host.innerHTML=`<div class="sdk-map" role="region" aria-label="${e(this.t('map'))}"></div><div class="map-state" role="status">${e(this.t('mapLoading'))}</div><div class="map-controls">${[['plus','zoomIn'],['minus','zoomOut'],['fit','fitRoute'],['location','locate']].map(([ico,label])=>`<button data-map="${ico}" aria-label="${e(this.t(label))}">${icon(ico)}</button>`).join('')}</div><div class="map-legend"></div>`;
  host.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{const a=b.dataset.map;if(a==='location')return this.onLocate?.();if(!this.map)return;if(a==='fit')this.fit();else this.map.setZoom(this.map.getZoom()+(a==='plus'?1:-1));});this.init();
 }
 async init(){try{this.AMap=await loadSDK(this.jsKey);if(this.destroyed)return;
  this.map=new this.AMap.Map(this.host.querySelector('.sdk-map'),{viewMode:'2D',lang:this.lang==='en'?'en':'zh_cn',zoom:this.viewport?.zoom||14,center:this.viewport?.center||[121.47,31.23],resizeEnable:true,showLabel:true,keyboardEnable:true});
  this.layers=new MapLayers(this.map);this.map.on('click',event=>{if(this.pickPoint)this.onPoint?.({lat:event.lnglat.getLat(),lng:event.lnglat.getLng(),coordinate_system:'GCJ02'});});
  this.map.on('complete',()=>{if(!this.destroyed){this.host.querySelector('.map-state').textContent='';this.host.dataset.mapReady='true';this.localizeCredits();}});
  this.update(this);if(!this.viewport)this.fit();if(this.pendingFocus)this.focus(this.pendingFocus);
 }catch{if(!this.destroyed)this.host.querySelector('.map-state').textContent=this.t('mapUnavailable');}}
 update(options){Object.assign(this,options);if(!this.map)return;const A=this.AMap;
  this.layers.replace('main',JSON.stringify(this.legs),()=>this.legs.flatMap(leg=>{const live=leg.status==='AVAILABLE'&&leg.polyline?.length;const path=live?leg.polyline:leg.origin&&leg.destination?[[leg.origin.lng,leg.origin.lat],[leg.destination.lng,leg.destination.lat]]:null;return path?[new A.Polyline({...routeStyle,path,strokeStyle:live?'solid':'dashed',showDir:!!live,strokeOpacity:live?1:.45})]:[];}));
  const points=this.stops.map((s,i)=>{const p=this.catalogue.find(p=>p.id===s.poi_id),c=s.estimated_coordinates||p?.coordinates;return c?{id:s.poi_id,position:[c[1],c[0]],name:poiName(p||s,this.lang),label:String(i+1).padStart(2,'0'),end:i===this.stops.length-1}:null;}).filter(Boolean);
  points.push(...this.nearby.filter(p=>p.location).map(p=>({id:p.service_poi_id,position:[p.location.lng,p.location.lat],name:p.name,label:'•',service:true})));
  if(this.entrance)points.push({id:'__entrance__',position:[this.entrance.lng,this.entrance.lat],name:this.entrance.label,label:'↳',entrance:true});
  this.layers.replace('pois',JSON.stringify(points),()=>{this.markers.clear();return points.map(p=>this.marker(p));});
  const user=this.userLocation;
  this.layers.replace('user',JSON.stringify([user,this.heading,this.t('yourLocation')]),()=>{this.markers.delete('__user__');if(!user)return [];const objects=[this.marker({id:'__user__',position:[user.lng,user.lat],name:this.t('yourLocation'),label:this.heading==null?'•':'↑',user:true})];if(Number.isFinite(user.accuracy)&&user.accuracy>0&&user.accuracy<=50)objects.unshift(new A.Circle({center:[user.lng,user.lat],radius:user.accuracy,fillColor:'#8053DB',fillOpacity:.12,strokeOpacity:0,zIndex:60}));return objects;});
  for(const kind of ['start_access','nearby_detour']){const r=this.guidance?.kind===kind||kind==='nearby_detour'&&this.guidance?.kind==='return_to_route'?this.guidance:null;
   const changed=this.layers.replace(kind,JSON.stringify(r),()=>!r||r.availability!=='AVAILABLE'?[]:[...r.segments.map(s=>new A.Polyline({...auxiliaryStyle(kind),path:s.polyline,strokeStyle:kind==='nearby_detour'||s.kind==='walking'&&r.mode==='transit'?'dashed':'solid'})),new A.Marker({position:[r.destination.lng,r.destination.lat],content:`<span class="guidance-target ${kind}">↳</span>`,zIndex:135}),new A.Marker({position:[r.origin.lng,r.origin.lat],content:`<span class="guidance-origin ${kind}">○</span>`,zIndex:130})]);
   if(changed&&r)this.map.setFitView([...this.layers.objects('main'),...this.layers.objects(kind)],false,[80,65,100,65],17);
  }
  for(const [id,{b}] of this.markers)b.classList.toggle('selected',id===this.selected);
  this.host.classList.toggle('picking-origin',!!this.pickPoint);
  this.host.querySelector('.map-legend').innerHTML=`<i class="legend-main"></i>${e(this.t('yourWalk'))} ${this.guidance?`<i class="legend-${this.guidance.kind==='start_access'?'access':'detour'}"></i>${e(this.t(this.guidance.kind==='start_access'?'gettingThere':'nearbyDetour'))}`:''}${this.legs.some(l=>l.status!=='AVAILABLE')?` · ${e(this.t('approximate'))}`:''}`;
 }
 marker(p){const b=document.createElement('button');b.className=`route-marker ${p.service?'service-marker':''} ${p.entrance?'entrance-marker':''} ${p.user?'user-marker':''} ${p.end?'end-marker':''}`;b.dataset.marker=p.id;b.setAttribute('aria-label',`${p.label} ${p.name}`);b.innerHTML=`<span ${p.user&&this.heading!=null?`style="transform:rotate(${Number(this.heading)}deg)"`:''}>${e(p.label)}</span><span class="marker-label">${e(p.name)}</span>`;b.onclick=event=>{event.stopPropagation();if(!p.user)this.onSelect?.(p.id);};b.onmouseenter=b.onfocus=()=>this.onHover?.(p.id);b.onmouseleave=b.onblur=()=>this.onHover?.(null);const marker=new this.AMap.Marker({position:p.position,content:b,anchor:'center',zIndex:p.user?150:120});this.markers.set(p.id,{marker,b});return marker;}
 localizeCredits(){if(this.lang!=='en')return;const logo=this.host.querySelector('.amap-logo');if(logo){logo.textContent='AMap';logo.setAttribute('aria-label','AMap');logo.title='AMap';}const code=this.host.querySelector('.amap-mcode');if(code)code.textContent=code.textContent.replace('号','');}
 fit(){if(this.map)this.map.setFitView([...this.layers.objects('main'),...this.layers.objects('pois')],false,[70,70,90,70],17);}
 highlight(id){for(const [key,{b}] of this.markers)b.classList.toggle('hovered',key===id);}
 focus(id){const item=this.markers.get(id);if(!item){this.pendingFocus=id;return;}this.map.setZoomAndCenter(Math.max(15,this.map.getZoom()),item.marker.getPosition());}
 getViewport(){const c=this.map?.getCenter();return c?{provider:'sdk',center:[c.lng,c.lat],zoom:this.map.getZoom()}:this.viewport;}
 destroy(){this.destroyed=true;this.layers?.destroy();this.map?.destroy();}
}

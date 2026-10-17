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
 constructor(host,options){Object.assign(this,options);this.host=host;this.markers=new Map();this.viewport=options.viewport?.provider==='sdk'?options.viewport:null;
  host.innerHTML=`<div class="sdk-map" role="region" aria-label="${e(this.t('map'))}"></div><div class="map-state" role="status">${e(this.t('mapLoading'))}</div><div class="map-controls">${[['plus','zoomIn'],['minus','zoomOut'],['fit','fitRoute'],['location','locate']].map(([ico,label])=>`<button data-map="${ico}" aria-label="${e(this.t(label))}">${icon(ico)}</button>`).join('')}</div><div class="map-legend"><span></span>${e(this.t(this.legs.some(l=>l.status==='AVAILABLE')?'mapReal':'mapEstimate'))}</div>`;
  host.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{const a=b.dataset.map;if(a==='location')return this.onLocate?.();if(!this.map)return;if(a==='fit')this.fit();else this.map.setZoom(this.map.getZoom()+(a==='plus'?1:-1));});
  this.init();
 }
 async init(){try{const AMap=await loadSDK(this.jsKey);if(this.destroyed)return;
  this.map=new AMap.Map(this.host.querySelector('.sdk-map'),{viewMode:'2D',lang:this.lang==='en'?'en':'zh_cn',zoom:this.viewport?.zoom||14,center:this.viewport?.center||[121.47,31.23],resizeEnable:true,showLabel:true,keyboardEnable:true});
  this.map.on('complete',()=>{if(!this.destroyed){this.host.querySelector('.map-state').textContent='';this.host.dataset.mapReady='true';this.localizeCredits();}});
  this.overlays=[];
  for(const leg of this.legs){let path=leg.status==='AVAILABLE'?leg.polyline:null;const live=!!path?.length;if(!live&&leg.origin&&leg.destination)path=[[leg.origin.lng,leg.origin.lat],[leg.destination.lng,leg.destination.lat]];if(!path?.length)continue;const line=new AMap.Polyline({path,strokeColor:'#a77db9',strokeWeight:5,strokeStyle:live?'solid':'dashed',strokeOpacity:.9,zIndex:45});this.map.add(line);this.overlays.push(line);}
  const points=this.stops.map((s,i)=>{const p=this.catalogue.find(p=>p.id===s.poi_id);const c=s.estimated_coordinates||p?.coordinates;return c?{id:s.poi_id,position:[c[1],c[0]],name:poiName(p,this.lang),label:String(i+1).padStart(2,'0')}:null;}).filter(Boolean);
  points.push(...this.nearby.map(p=>({id:p.service_poi_id,position:[p.location.lng,p.location.lat],name:p.name,label:'•',service:true})));
  if(this.entrance)points.push({id:'__entrance__',position:[this.entrance.lng,this.entrance.lat],name:this.entrance.label,label:'↳',entrance:true});
  if(this.userLocation)points.push({id:'__user__',position:[this.userLocation.lng,this.userLocation.lat],name:this.t('yourLocation'),label:'•',service:true});
  for(const p of points){const b=document.createElement('button');b.className=`route-marker ${p.service?'service-marker':''} ${p.entrance?'entrance-marker':''} ${p.id===this.selected?'selected':''}`;b.dataset.marker=p.id;b.setAttribute('aria-label',`${p.label} ${p.name}`);b.innerHTML=`<span>${e(p.label)}</span><span class="marker-label">${e(p.name)}</span>`;b.onclick=()=>{if(p.id!=='__user__')this.onSelect?.(p.id);};b.onmouseenter=b.onfocus=()=>this.onHover?.(p.id);b.onmouseleave=b.onblur=()=>this.onHover?.(null);const marker=new AMap.Marker({position:p.position,content:b,anchor:'center',zIndex:p.id===this.selected?130:120});this.map.add(marker);this.markers.set(p.id,{marker,b});this.overlays.push(marker);}
  if(!this.viewport)this.fit();if(this.pendingFocus)this.focus(this.pendingFocus);
 }catch{if(!this.destroyed)this.host.querySelector('.map-state').textContent=this.t('mapUnavailable');}}
 localizeCredits(){if(this.lang!=='en')return;const logo=this.host.querySelector('.amap-logo');if(logo){logo.textContent='AMap';logo.setAttribute('aria-label','AMap');logo.title='AMap';}const code=this.host.querySelector('.amap-mcode');if(code)code.textContent=code.textContent.replace('号','');}
 fit(){if(this.map&&this.overlays.length)this.map.setFitView(this.overlays,false,[70,70,90,70],17);}
 highlight(id){for(const [key,{b}] of this.markers)b.classList.toggle('hovered',key===id);}
 focus(id){const item=this.markers.get(id);if(!item){this.pendingFocus=id;return;}this.map.setZoomAndCenter(Math.max(15,this.map.getZoom()),item.marker.getPosition());for(const [key,{b}] of this.markers)b.classList.toggle('selected',key===id);}
 getViewport(){const c=this.map?.getCenter();return c?{provider:'sdk',center:[c.lng,c.lat],zoom:this.map.getZoom()}:this.viewport;}
 destroy(){this.destroyed=true;this.map?.destroy();}
}

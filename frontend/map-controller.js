import {SDKMapController} from './amap-sdk.js';
import {project,unproject,escapeHTML as e,poiName} from './lib.js';
import {icon} from './components.js';
export class MapController {
 constructor(host,{stops=[],legs=[],nearby=[],catalogue=[],lang='en',t,live=false,jsKey='',userLocation=null,entrance=null,selected=null,onSelect,onHover,onLocate,viewport=null}) {
  if(jsKey)return new SDKMapController(host,{stops,legs,nearby,catalogue,lang,t,live,jsKey,userLocation,entrance,selected,onSelect,onHover,onLocate,viewport});
  if(lang==='en')live=false;
  Object.assign(this,{host,stops,legs,nearby,catalogue,lang,t,live,userLocation,entrance,selected,onSelect,onHover,onLocate});
  this.center=viewport?.center||[121.47,31.23];this.zoom=viewport?.zoom||13;this.failed=viewport?.failed||false;
  this.host.innerHTML=`<div class="map-surface" tabindex="0" role="region" aria-label="${e(t('map'))}"><img class="basemap" alt="" hidden><svg class="map-lines" aria-hidden="true"></svg><div class="map-markers"></div><div class="map-state" role="status"></div></div>
  <div class="map-top-label"><span class="map-dot"></span>${e(t('location'))}</div><div class="map-controls">${[['plus','zoomIn'],['minus','zoomOut'],['fit','fitRoute'],['location','locate']].map(([ico,label])=>`<button aria-label="${e(t(label))}" title="${e(t(label))}" data-map="${ico}">${icon(ico)}</button>`).join('')}</div><div class="map-legend"><span></span>${e(t(legs.some(l=>l.status==='AVAILABLE')?'mapReal':'mapEstimate'))}</div><small class="map-attribution">${e(t('mapAttribution'))}</small>`;
  this.surface=host.querySelector('.map-surface');this.markerLayer=host.querySelector('.map-markers');this.img=host.querySelector('img');this.lines=host.querySelector('svg.map-lines');
  this.resize=new ResizeObserver(()=>{if(!this.width){this.measure();if(!viewport)this.fit(false);}this.measure();this.draw();this.loadBase();});this.resize.observe(host);
  host.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{const a=b.dataset.map;if(a==='location')return this.onLocate?.();if(a==='fit')this.fit();else {this.zoom=Math.max(10,Math.min(17,this.zoom+(a==='plus'?1:-1)));this.draw();this.loadBase();}});
  this.surface.onpointerdown=event=>{if(event.target.closest('button'))return;this.drag={x:event.clientX,y:event.clientY,center:project(...this.center,this.zoom)};this.surface.setPointerCapture(event.pointerId);};
  this.surface.onpointermove=event=>{if(!this.drag)return;const x=(event.clientX-this.drag.x)*this.width/host.clientWidth,y=(event.clientY-this.drag.y)*this.height/host.clientHeight;this.center=unproject(this.drag.center[0]-x,this.drag.center[1]-y,this.zoom);this.img.style.transform=`translate(${event.clientX-this.drag.x}px,${event.clientY-this.drag.y}px)`;this.draw();};
  this.surface.onpointerup=()=>{if(this.drag){this.drag=null;this.loadBase();}};
  this.surface.onpointercancel=()=>{this.drag=null;this.loadBase();};
  this.surface.onkeydown=event=>{const delta={ArrowLeft:[-90,0],ArrowRight:[90,0],ArrowUp:[0,-90],ArrowDown:[0,90]}[event.key];if(!delta)return;event.preventDefault();const c=project(...this.center,this.zoom);this.center=unproject(c[0]+delta[0],c[1]+delta[1],this.zoom);this.draw();this.loadBase();};
 }
 measure(){this.width=Math.max(100,Math.min(1024,this.host.clientWidth));this.height=Math.max(100,Math.min(1024,this.host.clientHeight));}
 points(){return this.stops.map((s,i)=>{const p=this.catalogue.find(p=>p.id===s.poi_id);const coords=s.estimated_coordinates||p?.coordinates;return coords?{id:s.poi_id,coords:[coords[1],coords[0]],number:i+1,name:poiName(p||s,this.lang)}:null;}).filter(Boolean);}
 fit(load=true){const points=this.points();if(!points.length)return;this.measure();const xs=points.map(p=>p.coords[0]),ys=points.map(p=>p.coords[1]);this.center=[(Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2];this.zoom=16;
  for(let z=16;z>=10;z--){const p=points.map(p=>project(...p.coords,z)),dx=Math.max(...p.map(a=>a[0]))-Math.min(...p.map(a=>a[0])),dy=Math.max(...p.map(a=>a[1]))-Math.min(...p.map(a=>a[1]));if(dx<this.width*.64&&dy<this.height*.64){this.zoom=z;break;}}
  this.draw();if(load)this.loadBase();
 }
 pos(point){const c=project(...this.center,this.zoom),p=project(...point,this.zoom);return [p[0]-c[0]+this.width/2,p[1]-c[1]+this.height/2];}
 draw(){if(!this.width)return;this.lines.setAttribute('viewBox',`0 0 ${this.width} ${this.height}`);this.lines.setAttribute('preserveAspectRatio','none');
  this.lines.innerHTML=this.legs.map(leg=>{let points=leg.status==='AVAILABLE'?leg.polyline:null;const fallback=!points?.length;if(fallback&&leg.origin&&leg.destination)points=[[leg.origin.lng,leg.origin.lat],[leg.destination.lng,leg.destination.lat]];
    if(!points?.length)return '';return `<polyline points="${points.map(p=>this.pos(p).join(',')).join(' ')}" class="route-line ${fallback?'estimated':''} ${leg.to_poi_id===this.selected?'selected':''}"/>`;}).join('');
  const points=[...this.points(),...(this.entrance?[{id:'__entrance__',coords:[this.entrance.lng,this.entrance.lat],name:this.entrance.label,entrance:true}]:[]),...(this.userLocation?[{id:'__user__',coords:[this.userLocation.lng,this.userLocation.lat],name:this.t('yourLocation'),service:true}]:[]),...this.nearby.map(p=>({id:p.service_poi_id,coords:[p.location.lng,p.location.lat],name:p.name,service:true}))];
  this.markerLayer.innerHTML=points.map(p=>{const [x,y]=this.pos(p.coords);return `<button class="route-marker ${p.service?'service-marker':''} ${p.entrance?'entrance-marker':''} ${p.id===this.selected?'selected':''}" style="left:${x/this.width*100}%;top:${y/this.height*100}%" data-marker="${e(p.id)}" aria-label="${e(`${p.number||''} ${p.name}`)}" aria-pressed="${p.id===this.selected}"><span>${p.entrance?'↳':p.service?'•':String(p.number).padStart(2,'0')}</span><span class="marker-label">${e(p.name)}</span></button>`;}).join('');
  this.markerLayer.querySelectorAll('button').forEach(b=>{b.onclick=()=>{if(b.dataset.marker!=='__user__')this.onSelect?.(b.dataset.marker);};b.onmouseenter=b.onfocus=()=>this.onHover?.(b.dataset.marker);b.onmouseleave=b.onblur=()=>this.onHover?.(null);});
 }
 highlight(id){this.markerLayer.querySelectorAll('[data-marker]').forEach(b=>b.classList.toggle('hovered',b.dataset.marker===id));}
 focus(id){const p=(id==='__entrance__'&&this.entrance?{coords:[this.entrance.lng,this.entrance.lat]}:null)||(id==='__user__'&&this.userLocation?{coords:[this.userLocation.lng,this.userLocation.lat]}:null)||this.points().find(p=>p.id===id)||this.nearby.map(p=>({id:p.service_poi_id,coords:[p.location.lng,p.location.lat]})).find(p=>p.id===id);if(p){this.center=p.coords;this.zoom=Math.max(15,this.zoom);this.selected=id;this.draw();this.loadBase();}}
 unavailable(){const status=this.host.querySelector('.map-state');status.textContent=this.t(this.lang==='en'?'englishMapUnavailable':'mapUnavailable');if(this.live){const retry=document.createElement('button');retry.textContent=this.t('retry');retry.className='map-retry';retry.onclick=()=>{this.failed=false;this.lastQuery=null;this.loadBase();};status.append(retry);}}
 loadBase(){clearTimeout(this.timer);if(this.destroyed)return;if(!this.live||this.failed){this.unavailable();return;}
  this.timer=setTimeout(async()=>{if(this.destroyed)return;this.center=[Math.max(120,Math.min(123,this.center[0])),Math.max(30,Math.min(32,this.center[1]))];const query=new URLSearchParams({lng:this.center[0].toFixed(6),lat:this.center[1].toFixed(6),zoom:this.zoom,width:Math.round(this.width),height:Math.round(this.height)}).toString();if(query===this.lastQuery)return;this.lastQuery=query;
   this.abort?.abort();this.abort=new AbortController();this.img.hidden=true;this.host.querySelector('.map-state').textContent=this.t('mapLoading');
   try{const response=await fetch(`/api/map?${query}`,{signal:this.abort.signal});if(!response.ok)throw Error();const blob=await response.blob();if(this.destroyed)return;URL.revokeObjectURL(this.imageUrl);this.imageUrl=URL.createObjectURL(blob);this.img.src=this.imageUrl;this.img.hidden=false;this.img.style.transform='';this.host.querySelector('.map-state').textContent='';}
   catch(error){if(error.name==='AbortError')return;this.failed=true;this.img.hidden=true;this.img.style.transform='';this.unavailable();}
  },250);
 }
 getViewport(){return {center:this.center,zoom:this.zoom,failed:this.failed};}
 destroy(){this.destroyed=true;clearTimeout(this.timer);this.abort?.abort();this.resize.disconnect();URL.revokeObjectURL(this.imageUrl);}
}

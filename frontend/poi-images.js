import {safeAsset,poiName} from './lib.js';
export function safePoiImageUrl(value,source){
 const local=safeAsset(value);if(local)return local;
 if(source!=='AMAP'||typeof value!=='string')return null;
 try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&['amap.com','autonavi.com'].some(h=>u.hostname===h||u.hostname.endsWith('.'+h))?u.href:null;}catch{return null;}
}
// Shared by Atlas, picker, route thumbnails and details; no route sorting or scoring.
export function resolvePoiImage(poiId,{manifest,curated={},poi,lang='en'}={}){
 const row=manifest?.records?.find(r=>r.poi_id===poiId),slot=curated[poiId];
 const alt=poiName(poi,lang),theme=slot?.theme||['stone','sage','clay','blue','amber'][Number(poiId?.replace('p','')||0)%5]||'stone';
 const fallback={src:null,source:'FALLBACK',status:'FALLBACK',alt,theme};
 const selected=safeAsset(slot?.src);if(selected)return {...fallback,src:selected,source:'CURATED',status:'AVAILABLE'};
 if(row?.route_role==='anchor'&&row.source!=='CURATED')return fallback;
 const src=safePoiImageUrl(row?.image_url,row?.source);
 if(src&&row.status==='AVAILABLE'&&(row.source==='CURATED'||row.reviewed===true))return {...fallback,src,source:row.source,status:'AVAILABLE'};
 return fallback;
}
export function bindImageFallbacks(root){
 root.addEventListener('error',event=>{const img=event.target;if(img.tagName==='IMG'&&img.closest('.image-slot')){img.parentElement.dataset.imageState='FALLBACK';img.remove();}},true);
}

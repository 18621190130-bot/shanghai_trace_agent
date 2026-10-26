// Planning may use a coarse fix with consent; arrival detection still requires 50m.
export function planningFix(position,now=Date.now()){
 const c=position?.coords;
 if(!c||![c.latitude,c.longitude,c.accuracy,position.timestamp].every(Number.isFinite)||c.accuracy<0||c.accuracy>5000||Math.abs(c.latitude)>90||Math.abs(c.longitude)>180||now-position.timestamp>60000||now-position.timestamp< -5000)return 'invalid';
 return c.accuracy<=50?'precise':'approximate';
}
export function acquirePlanningLocation(geo,{timeout=12000,onResult,onError}={}){
 let best=null,id,finished=false;
 const cancel=()=>{finished=true;clearTimeout(timer);if(id!==undefined)geo.clearWatch(id);};
 const finish=error=>{if(finished)return;cancel();if(best)onResult(best);else onError(error||'gpsLowQuality');};
 const timer=setTimeout(()=>finish('gpsTimeout'),timeout);
 try{id=geo.watchPosition(p=>{const quality=planningFix(p);if(quality==='invalid')return;if(!best||p.coords.accuracy<best.coords.accuracy)best=p;if(quality==='precise')finish();},err=>finish(err.code===1?'gpsDenied':err.code===3?'gpsTimeout':'gpsUnavailable'),{enableHighAccuracy:true,maximumAge:0,timeout});}catch{finish('gpsUnavailable');}
 if(finished&&id!==undefined)geo.clearWatch(id);
 return cancel;
}

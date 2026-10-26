export function movementHeading(coords){return Number.isFinite(coords.heading)&&Number.isFinite(coords.speed)&&coords.speed>=.8&&coords.accuracy<=50?((coords.heading%360)+360)%360:null;}
export function absoluteHeading(event,screenAngle=0){
 let value=null;
 if(Number.isFinite(event.webkitCompassHeading)&&Number.isFinite(event.webkitCompassAccuracy)&&event.webkitCompassAccuracy>=0&&event.webkitCompassAccuracy<=30)value=event.webkitCompassHeading;
 else if(event.absolute===true&&Number.isFinite(event.alpha))value=360-event.alpha;
 return value===null?null:((value+screenAngle)%360+360)%360;
}
export class HeadingTracker {
 constructor(onChange){this.onChange=onChange;this.last=null;this.at=0;this.handler=e=>{const now=Date.now(),angle=absoluteHeading(e,globalThis.screen?.orientation?.angle||0);if(angle===null||now-this.at<150)return;const delta=this.last===null?0:((angle-this.last+540)%360)-180;this.last=this.last===null?angle:(this.last+delta*.25+360)%360;this.at=now;this.onChange({angle:this.last,source:'device',timestamp:now});clearTimeout(this.expiry);this.expiry=setTimeout(()=>{this.last=null;this.onChange(null);},5000);};}
 async enable(){if(!globalThis.isSecureContext)return false;const api=globalThis.DeviceOrientationEvent;if(!api)return false;try{if(api.requestPermission&&await api.requestPermission()!=='granted')return false;this.stop();window.addEventListener('deviceorientationabsolute',this.handler);window.addEventListener('deviceorientation',this.handler);this.enabled=true;return true;}catch{return false;}}
 stop(){if(globalThis.window){window.removeEventListener('deviceorientationabsolute',this.handler);window.removeEventListener('deviceorientation',this.handler);}clearTimeout(this.expiry);this.enabled=false;this.last=null;}
}

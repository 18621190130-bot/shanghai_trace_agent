"""Offline browser acceptance using an explicit fake SDK and guidance fixtures. Requires Playwright + Edge."""
import os,subprocess,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from http.server import ThreadingHTTPServer
os.environ.update(AMAP_WEB_SERVICE_KEY='',AMAP_API_KEY='',DEEPSEEK_API_KEY='',AMAP_JS_API_KEY='',AMAP_JS_SECURITY_CODE='')
from web_server import handler_for
from src.web_app import WebApplication
server=ThreadingHTTPServer(('127.0.0.1',8824),handler_for(WebApplication()))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
code=r"""
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({channel:'msedge',headless:true});try{
 const p=await b.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.route('https://**/*',r=>r.abort());
 await p.addInitScript(()=>{window.mapInstances=0;class Overlay{constructor(o){this.o=o;}getPosition(){return this.o.position;}}window.AMap={Polyline:Overlay,Marker:Overlay,Circle:Overlay,Map:class{constructor(host,o){window.mapInstances++;window.testMap=this;this.host=host;this.options=o;this.objects=new Set();this.events={};host.innerHTML='<div style="position:absolute;inset:0;background:#e8ece4"></div>';host.onclick=()=>this.events.click?.({lnglat:{getLat:()=>31.21,getLng:()=>121.45}});}on(n,fn){this.events[n]=fn;if(n==='complete')setTimeout(fn,10);}add(xs){for(const x of Array.isArray(xs)?xs:[xs])this.objects.add(x);}remove(xs){for(const x of xs)this.objects.delete(x);}setFitView(){}getCenter(){return {lng:121.45,lat:31.21};}getZoom(){return 14;}setZoom(){}setZoomAndCenter(){}destroy(){}}};});
 await p.route('**/api/bootstrap',async r=>{const res=await r.fetch(),d=await res.json();d.capabilities.map_js_key='TEST';await r.fulfill({json:d});});
 await p.route('**/api/guidance/route',async r=>{const q=r.request().postDataJSON();await r.fulfill({json:{...q,availability:'AVAILABLE',duration_s:{walking:700,transit:450,taxi:300,bicycle:400}[q.mode],distance_m:1200,segments:[{kind:q.mode,polyline:[[q.origin.lng,q.origin.lat],[q.destination.lng,q.destination.lat]]}],steps:[]}});});
 await p.route('**/api/nearby',r=>r.fulfill({json:{status:'AVAILABLE',results:[{service_poi_id:'amap:test',name:'Test Cafe',name_en:'Test Cafe',primary_category:'CAFE',distance_m:100,location:{lat:31.21,lng:121.455,coordinate_system:'GCJ02'}}]}}));
 await p.goto('http://127.0.0.1:8824/#plan');await p.waitForSelector('#setup-form');await p.locator('#setup-form button[type=submit]').click();await p.waitForSelector('[data-action=nav-open]');
 const initialIds=await p.locator('.stop-button').evaluateAll(es=>es.map(e=>e.dataset.value));await p.locator('[data-action=nav-open]').click();await p.locator('[data-action=nav-pick]').click();await p.locator('.sdk-map').click({position:{x:350,y:300}});await p.waitForSelector('.transport-option');assert.equal(await p.locator('.transport-option').count(),4);assert.equal(await p.evaluate(()=>mapInstances),1);
 const mainBefore=await p.evaluate(()=>[...testMap.objects].filter(o=>o.o.strokeColor==='#8053DB').length);assert.ok(mainBefore>0);await p.locator('[data-action=nav-mode][data-value=transit]').click();assert.equal(await p.evaluate(()=>[...testMap.objects].filter(o=>o.o.strokeColor==='#8053DB').length),mainBefore);
 await p.locator('[data-action=nav-direction][data-value=reverse]').click();await p.waitForFunction(id=>document.querySelector('.stop-button').dataset.value===id,initialIds.at(-1));assert.deepEqual(await p.locator('.stop-button').evaluateAll(es=>es.map(e=>e.dataset.value)),[...initialIds].reverse());
 await p.locator('[data-action=nav-direction][data-value=original]').click();await p.waitForFunction(id=>document.querySelector('.stop-button').dataset.value===id,initialIds[0]);
 await p.route('**/api/guidance/search',r=>r.fulfill({json:{results:[{name:'Cloud Nine (Zhongshan Park)',name_en:'Cloud Nine (Zhongshan Park)',address:'1018 Changning Road, Changning, Shanghai',address_en:'1018 Changning Road, Changning, Shanghai',location:{lat:31.22,lng:121.42,coordinate_system:'GCJ02'}}]}}));
 await p.waitForFunction(()=>!document.querySelector('[data-action=nav-direction]').disabled);await p.locator('#origin-query').evaluate(el=>{el.value='Cloud Nine';el.form.requestSubmit();});await p.waitForSelector('.origin-result');assert.match(await p.locator('.origin-result').innerText(),/1018 Changning/);assert.doesNotMatch(await p.locator('.origin-result').innerText(),/121\.42|31\.22/);
 let firstDestination;
 await p.route('**/api/guidance/route',r=>{const q=r.request().postDataJSON(),key=JSON.stringify(q.destination);firstDestination??=key;const original=key===firstDestination;return r.fulfill({json:{...q,availability:'AVAILABLE',duration_s:original?{walking:4000,transit:2400,taxi:300,bicycle:2000}[q.mode]:{walking:2000,transit:900,taxi:200,bicycle:1000}[q.mode],distance_m:1200,segments:[{kind:q.mode,polyline:[[q.origin.lng,q.origin.lat],[q.destination.lng,q.destination.lat]]}],steps:[]}});});
 await p.locator('.origin-result').click();await p.waitForFunction(id=>document.querySelector('.stop-button').dataset.value===id,initialIds.at(-1));await p.waitForSelector('.transport-option');assert.match(await p.locator('.selected-origin').innerText(),/Cloud Nine/);assert.equal(await p.locator('[data-action=nav-baseline]').count(),0);assert.ok(await p.evaluate(()=>[...testMap.objects].some(o=>o.o.strokeColor==='#397DE0'&&o.o.isOutline===false)));
 await p.locator('[data-action=nav-direction][data-value=original]').click();await p.waitForFunction(id=>document.querySelector('.stop-button').dataset.value===id,initialIds[0]);
 await p.screenshot({path:'.runtime/smart-start-desktop.png'});await p.locator('.smart-start [data-action=start]').click();await p.waitForSelector('[data-action=arrive-manual]');assert.equal(await p.locator('.smart-start').count(),0);
 await p.locator('[data-action=arrive-manual]').click();await p.waitForSelector('.arrival-card');await p.locator('[data-action=arrival-nearby]').click();await p.waitForSelector('[data-action=nav-directions]');await p.locator('[data-action=nav-directions]').click();await p.waitForSelector('[data-action=nav-back]');assert.deepEqual(await p.locator('.stop-button').evaluateAll(es=>es.map(e=>e.dataset.value)),initialIds);assert.ok(await p.evaluate(()=>[...testMap.objects].some(o=>o.o.strokeColor==='#8053DB')));assert.ok(await p.evaluate(()=>[...testMap.objects].some(o=>o.o.strokeColor==='#20A89A')));
 await p.locator('[data-action=nav-return]').click();await p.waitForSelector('[data-action=nav-back]');await p.locator('[data-action=nav-back]').click();assert.equal(await p.evaluate(()=>[...testMap.objects].filter(o=>o.o.strokeColor==='#20A89A').length),0);
 await p.setViewportSize({width:390,height:844});await p.screenshot({path:'.runtime/smart-start-mobile.png'});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);console.log('PASS browser: real route generation, preserved SDK instance, 4 modes, full reversal and restore, arrival, nearby and return layers, mobile, no page errors');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
"""
env=os.environ.copy();env['NODE_PATH']=r'C:\Users\huawei\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
try:
 result=subprocess.run(['node','-'],input=code,text=True,env=env,timeout=60)
 if result.returncode:raise SystemExit(result.returncode)
finally:server.shutdown();server.server_close();thread.join()

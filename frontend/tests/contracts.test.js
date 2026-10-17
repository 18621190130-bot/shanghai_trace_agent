import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {messages,translator} from '../i18n.js';
import {escapeHTML,walkingMetrics,remaining,project,unproject,safeAsset,amapLink,walkSummary} from '../lib.js';
import {culturalBridge,imageSlot} from '../components.js';

test('English and Chinese expose the same complete UI vocabulary',()=>{
 assert.deepEqual(Object.keys(messages.en).sort(),Object.keys(messages.zh).sort());
 for(const strings of Object.values(messages))for(const value of Object.values(strings))assert.ok(typeof value==='string'&&value.length);
});
test('Every static translation reference exists',()=>{
 const source=readFileSync(new URL('../app.js',import.meta.url),'utf8')+readFileSync(new URL('../components.js',import.meta.url),'utf8');
 for(const match of source.matchAll(/\bt\('([^']+)'\)/g))assert.ok(messages.en[match[1]],match[1]);
});
test('Provider names and editorial text cannot inject HTML',()=>{
 assert.equal(escapeHTML('<img onerror="alert(1)">'),'&lt;img onerror=&quot;alert(1)&quot;&gt;');
 assert.ok(culturalBridge({en:{bridge:'<script>bad</script>'}},'en',translator('en')).includes('&lt;script&gt;'));
});
test('Reserved images only accept local user-controlled assets',()=>{
 assert.equal(safeAsset('/assets/shanghai/walk.webp'),'/assets/shanghai/walk.webp');
 for(const path of ['https://remote/image.jpg','javascript:bad','/assets/../../secret','/src/file'])assert.equal(safeAsset(path),null);
 assert.ok(imageSlot({src:null},'Reserved').includes('slot-frame'));
});
test('Walking estimates are not labeled live',()=>{
 const result=walkingMetrics({walking_data_status:'FALLBACK_ESTIMATE',walking_distance_m:700,planning_distance_m:500,total_estimated_walking_minutes:8,total_estimated_minutes:55});
 assert.equal(result.live,false);assert.equal(result.metres,500);assert.equal(result.totalMinutes,55);
});
test('Live route summary uses real seconds and selected visit minutes',()=>{
 const result=walkingMetrics({walking_data_status:'AVAILABLE',walking_distance_m:1000,walking_duration_s:1200,total_stay_minutes:60,total_estimated_minutes:50});
 assert.equal(result.totalMinutes,80);assert.equal(result.walkingMinutes,20);assert.equal(result.live,true);
});
test('Progress excludes visited and skipped without mutating snapshot',()=>{
 const trip={active_route:{ordered_pois:[{poi_id:'p1'},{poi_id:'p2'},{poi_id:'p3'}]},visited_poi_ids:['p1'],skipped_poi_ids:['p2']};
 const before=JSON.stringify(trip);assert.deepEqual(remaining(trip),[{poi_id:'p3'}]);assert.equal(JSON.stringify(trip),before);
});
test('Map projection round-trips effective GCJ02 coordinates',()=>{
 for(const z of [10,14,17]){const actual=unproject(...project(121.463841,31.167682,z),z);assert.ok(Math.abs(actual[0]-121.463841)<1e-8);assert.ok(Math.abs(actual[1]-31.167682)<1e-8);}
});
test('External map handoff encodes names and uses the actual position',()=>{
 const url=new URL(amapLink({lng:121.46,lat:31.16},'咖啡 & more'));
 assert.equal(url.hostname,'uri.amap.com');assert.equal(url.searchParams.get('position'),'121.46,31.16');assert.equal(url.searchParams.get('name'),'咖啡 & more');
});
test('User editorial fills cover and anchors while missing-content fallback remains',()=>{
 const content=JSON.parse(readFileSync(new URL('../content.json',import.meta.url),'utf8'));
 assert.equal(content.hero.length,8);assert.ok(content.hero.every(slot=>safeAsset(slot.src))); 
 assert.equal(Object.keys(content.cultural_bridge.places).length,22);
 for(const c of Object.values(content.cultural_bridge.places)){assert.equal(c.provenance.source,'USER_DOCUMENT');assert.ok(c.en.paragraphs.length);assert.ok(c.zh.paragraphs.length);assert.ok(!culturalBridge(c,'en',translator('en')).includes('cultural-story reserved'));}
 assert.ok(culturalBridge({en:{paragraphs:['<script>alert(1)</script>']}},'en',translator('en')).includes('&lt;script&gt;'));
 assert.ok(culturalBridge(null,'en',translator('en')).includes('reserved'));
});

test("AMap staticmap projection matches provider anchor pixel scale",()=>{const center=project(121.464420,31.176241,15),anchor=project(121.463841,31.167682,15);assert.ok(Math.abs((anchor[0]-center[0])-(-26.9836))<.1);assert.ok(Math.abs((anchor[1]-center[1])-466.1)<1);});

test('Settlement uses wall-clock duration, excludes skipped from completion and deduplicates explored POIs',()=>{
 const trip={visited_poi_ids:['p28'],skipped_poi_ids:['p5'],active_route:{ordered_pois:[{poi_id:'p28'},{poi_id:'p5'},{poi_id:'p29'}]},event_history:[{event_type:'trip_started',timestamp:'2026-10-06T10:00:00+08:00'},{event_type:'trip_abandoned',timestamp:'2026-10-06T11:12:30+08:00'}],updated_at:'2026-10-06T11:12:30+08:00'};
 const value=walkSummary(trip,['p28','p4']);assert.equal(value.seconds,4350);assert.equal(value.rate,33);assert.equal(value.total,3);assert.deepEqual(value.explored,['p28','p4']);
});
test('Every Core POI has a display-only English overview and every reserved neighborhood has an introduction slot',()=>{
 const source=JSON.parse(readFileSync(new URL('../catalogue-en.json',import.meta.url),'utf8'));
 assert.equal(Object.keys(source.summaries).length,58);for(const text of [...Object.values(source.summaries),...Object.values(source.names)])assert.ok(!/[\u3400-\u9fff]/u.test(text));
 const c=JSON.parse(readFileSync(new URL('../content.json',import.meta.url),'utf8'));assert.equal(Object.keys(c.zones).length,4);for(const z of Object.values(c.zones)){assert.match(z.src,/^\/assets\/zones\/[a-z_]+\.jpg$/);assert.ok(readFileSync(new URL('..'+z.src,import.meta.url)).length>0);assert.equal(z.introduction.en,null);}
});

test('Distance preference converts metres without changing input data', async()=>{const {distance}=await import('../lib.js');assert.equal(distance(1609.344,'mi'),'1.0 mi');assert.equal(distance(800,'km'),'0.80 km');assert.equal(distance(800,'mi'),'0.50 mi');assert.equal(distance(null,'mi'),'—');});

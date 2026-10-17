/* Browser acceptance against the offline local adapter; no production fixtures. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.TRACEMATE_URL||'http://127.0.0.1:8765';
const checks=[];
const action=(p,a,v)=>p.locator(`[data-action="${a}"]:not(.detail-shade)${v===undefined?'':`[data-value="${v}"]`}`).first();
async function snapshot(p){return (await p.request.get(`${base}/api/bootstrap`)).json();}
async function ready(p){await p.waitForSelector('.workspace');await p.waitForFunction(()=>!document.querySelector('.weather-context')?.textContent.includes('Checking'));}
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);await page.waitForSelector('.hero');
 const transform=()=>page.locator('[data-orbit="0"]').evaluate(el=>el.style.transform);
 const first=await transform();await page.waitForTimeout(150);assert.notEqual(await transform(),first);
 await action(page,'motion').click();const paused=await transform();await page.waitForTimeout(150);assert.equal(await transform(),paused);checks.push('Orbit moves and pause stops it');
 await action(page,'plan').click();await page.waitForSelector('#setup-form');await action(page,'time',240).click();
 await action(page,'language').click();assert.equal(await action(page,'time',240).getAttribute('aria-pressed'),'true');assert.equal(await page.locator('html').getAttribute('lang'),'zh-CN');await action(page,'language').click();
 await page.locator('#setup-form [type="submit"]').click();await ready(page);
 let trip=(await snapshot(page)).trip;assert.equal(trip.status,'PLANNED');const pid=trip.active_route.ordered_pois[0].poi_id;
 await page.locator(`.stop-button[data-value="${pid}"]`).hover();assert.match(await page.locator(`[data-marker="${pid}"]`).getAttribute('class'),/hovered/);
 await page.locator(`[data-marker="${pid}"]`).click();await page.waitForSelector('.poi-detail');
 await action(page,'detail-tab','story').click();assert.equal(await page.locator('.cultural-story.reserved').count(),1);
 await page.keyboard.press('Escape');assert.equal(await page.locator('.poi-detail').count(),0);
 await action(page,'language').click();assert.equal((await snapshot(page)).trip.trip_id,trip.trip_id);await page.reload();await ready(page);assert.equal(await page.locator('html').getAttribute('lang'),'zh-CN');await action(page,'language').click();
 checks.push('Plan For Me, language persistence, map/list sync, reserved culture, reload');
 await action(page,'start').click();await ready(page);assert.equal((await snapshot(page)).trip.status,'ACTIVE');
 await action(page,'complete').click();await ready(page);trip=(await snapshot(page)).trip;assert.ok(trip.visited_poi_ids.includes(pid));
 const next=trip.active_route.ordered_pois.find(s=>!trip.visited_poi_ids.includes(s.poi_id));
 await action(page,'skip').click();await page.waitForSelector('dialog[open]');await action(page,'confirm-action').click();await ready(page);assert.ok((await snapshot(page)).trip.skipped_poi_ids.includes(next.poi_id));
 const before=(await snapshot(page)).trip;await action(page,'adjust').click();await page.locator('[name="minutes"]').fill('1');await page.locator('#replan-form [type="submit"]').click();await ready(page);assert.deepEqual((await snapshot(page)).trip,before);assert.equal(await page.locator('[role="alert"]').count(),1);
 await action(page,'end').click();await action(page,'confirm-action').click();await ready(page);assert.equal((await snapshot(page)).trip.status,'ABANDONED');checks.push('Start, complete, skip confirmation, failed replan rollback, end');
 await action(page,'plan').click();await action(page,'mode','places_in_mind').click();await action(page,'place','p28').click();await action(page,'place','p5').click();await page.locator('#setup-form [type="submit"]').click();await ready(page);
 trip=(await snapshot(page)).trip;assert.ok(['p28','p5'].every(id=>trip.active_route.ordered_pois.some(s=>s.poi_id===id)));checks.push('Places In Mind preserves both required places');
 await page.locator('.stop-button').first().click();await action(page,'detail-tab','nearby').click();await page.waitForSelector('[data-action="nearby-retry"]');assert.equal(await page.locator('.nearby-filters button').count(),7);checks.push('Nearby unavailable state, retry, seven categories');
 await action(page,'close-detail').click();
 await page.setViewportSize({width:390,height:844});await action(page,'mobile-view','map').click();await page.waitForSelector('.route-marker');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({animations:'disabled',path:'examples/frontend_4a/route-mobile.png'});
 await page.locator('.route-marker').first().click();await page.waitForSelector('.poi-detail');const box=await page.locator('.poi-detail').boundingBox();assert.ok(box.width<=390&&box.height<=844);await page.screenshot({animations:'disabled',path:'examples/frontend_4a/detail-mobile.png'});await action(page,'close-detail').click();checks.push('390px map tab and bottom sheet without horizontal overflow');
 const other=await browser.newPage({viewport:{width:768,height:1000},reducedMotion:'reduce'});other.on('pageerror',error=>errors.push(error.message));
 await other.goto(base+'/#plan');await other.waitForSelector('#setup-form');await action(other,'mode','surprise_me').click();await other.locator('[data-input="start"]').selectOption('p28');await action(other,'time',240).click();await other.locator('#setup-form [type="submit"]').click();await ready(other);assert.equal((await snapshot(other)).trip.current_intent.route_mode,'surprise_me');assert.equal(await other.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);checks.push('Surprise Me with actual engine, tablet layout');
 await other.goto(base);await other.waitForSelector('.hero');const reduced=await other.locator('[data-orbit="0"]').evaluate(el=>el.style.transform);await other.waitForTimeout(150);assert.equal(await other.locator('[data-orbit="0"]').evaluate(el=>el.style.transform),reduced);checks.push('Reduced motion stops orbit');
 assert.deepEqual(errors,[]);checks.push('No browser JavaScript errors');
 fs.writeFileSync('examples/frontend_4a/browser_checks.json',JSON.stringify({base,checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,checks,errors},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});

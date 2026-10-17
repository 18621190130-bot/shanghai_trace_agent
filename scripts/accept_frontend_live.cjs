/* Opt-in single final browser acceptance, using configured real providers. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const base=process.env.TRACEMATE_URL||'http://127.0.0.1:8766';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const report={base,generated_at:new Date().toISOString(),errors:[],responses:{}};
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('response',async response=>{const pathname=new URL(response.url()).pathname;if(['/api/reality','/api/nearby','/api/poi'].includes(pathname)){try{const data=await response.json();report.responses[pathname]=data;}catch{}}});
 await page.goto(base+'/#plan');await page.waitForSelector('#setup-form');
 const data=await (await page.request.get(base+'/api/bootstrap')).json();report.capabilities=data.capabilities;
 if(!data.capabilities.live_world)throw Error('Live provider is not configured; acceptance not performed.');
 await page.locator('[data-action="mode"][data-value="places_in_mind"]').click();
 await page.locator('[data-action="time"][data-value="240"]').click();
 for(const id of ['p28','p5'])await page.locator(`[data-action="place"][data-value="${id}"]`).click();
 await page.locator('#setup-form [type="submit"]').click();
 await page.waitForSelector('.workspace',{timeout:90000});
 await page.waitForFunction(()=>!document.querySelector('.weather-context')?.textContent.includes('Checking'),{},{timeout:60000});
 await page.waitForFunction(()=>document.querySelector('.basemap:not([hidden])')||document.querySelector('.map-state')?.textContent.includes('unavailable'),{},{timeout:30000});
 const trip=(await (await page.request.get(base+'/api/bootstrap')).json()).trip;
 report.trip={status:trip.status,stops:trip.active_route.ordered_pois.map(s=>s.poi_id),legs:trip.active_route.walking_legs.map(l=>({status:l.status,distance_m:l.distance_m,duration_s:l.duration_s,geometry_points:l.polyline?.length||0}))};
 report.basemap_available=await page.locator('.basemap:not([hidden])').count()>0;
 await page.screenshot({path:'examples/frontend_4a/route-live-desktop.png'});
 await page.locator('.stop-button').first().click();await page.waitForSelector('.detail-meta .status-text',{timeout:30000});
 await page.locator('[role="tab"][data-action="detail-tab"][data-value="nearby"]').click();
 await page.waitForFunction(()=>!document.querySelector('.panel-loading'),{},{timeout:45000});
 await page.screenshot({path:'examples/frontend_4a/nearby-live-desktop.png'});
 report.nearby_cards=await page.locator('.nearby-item').count();
 await page.locator('button[data-action="close-detail"]').click();
 await page.locator('[data-action="language"]').click();await page.screenshot({path:'examples/frontend_4a/route-live-zh.png'});
 await page.goto(base);await page.waitForSelector('.hero');await page.screenshot({path:'examples/frontend_4a/home-live-zh.png'});
 fs.writeFileSync('examples/frontend_4a/live_acceptance.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify({capabilities:report.capabilities,trip:report.trip,basemap_available:report.basemap_available,weather:report.responses['/api/reality']?.weather?.data_status,nearby:report.responses['/api/nearby']?.status,nearby_cards:report.nearby_cards,errors:report.errors},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1)});

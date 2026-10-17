const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const out=path.resolve('examples/frontend_4a');fs.mkdirSync(out,{recursive:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:8765');await page.waitForSelector('.hero');
 await page.screenshot({path:path.join(out,'home-desktop.png')});
 await page.getByRole('button',{name:'Plan my walk',exact:true}).first().click();await page.waitForSelector('#setup-form');
 await page.screenshot({path:path.join(out,'setup-desktop.png')});
 await page.getByRole('button',{name:'Find my walk',exact:true}).click();
 await page.waitForSelector('.workspace,.result-page',{timeout:30000});
 console.log('After generation:',await page.locator('h1').textContent());
 await page.screenshot({path:path.join(out,'route-desktop.png')});
 if(await page.locator('.workspace').count()){
  await page.locator('.stop-button').first().click();await page.waitForSelector('.poi-detail');
  await page.getByRole('tab',{name:'Cultural Bridge',exact:true}).click();
  await page.screenshot({path:path.join(out,'culture-desktop.png')});
  await page.getByRole('button',{name:'Close',exact:true}).click();
 }
 const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'reduce'});
 await mobile.goto('http://127.0.0.1:8765');await mobile.waitForSelector('.hero');
 await mobile.screenshot({path:path.join(out,'home-mobile.png')});
 console.log('Horizontal overflow:',await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
 console.log('Page errors:',errors);
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});

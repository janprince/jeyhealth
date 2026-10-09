/* Browser acceptance checks. Uses a separate seeded test server.
 * Start with a fresh database for each run:
 * JEYHEALTH_DB=/tmp/jeyhealth-ui.sqlite3 python3 server.py --port 8001
 * NODE_PATH=<playwright package parent> node tests/browser.cjs
 * Optional: JEYHEALTH_TEST_URL=http://127.0.0.1:8001
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const url = process.env.JEYHEALTH_TEST_URL || 'http://127.0.0.1:8001';
const output = path.resolve(__dirname, '../test-results');
fs.mkdirSync(output, {recursive:true});

(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const errors=[];
  async function login(role,viewport={width:1440,height:1000}){
    const context=await browser.newContext({viewport});
    const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));
    await p.goto(url);
    await p.locator(`[data-role="${role}"]`).click();
    await p.getByRole('button',{name:'Open my workspace'}).click();
    await p.locator('.workspace').waitFor();
    return p;
  }
  async function noOverflow(p,label){const widths=await p.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]);assert(widths[0]<=widths[1],`${label} overflows: ${widths}`)}
  const official=await login('official');
  await official.getByRole('heading',{name:'District overview'}).waitFor();
  await official.screenshot({path:path.join(output,'desktop-overview.png'),fullPage:true});
  assert.equal(await official.locator('.leaflet-interactive').count(),8);
  await official.locator('.leaflet-interactive').first().click();
  await official.locator('.leaflet-popup').waitFor();
  await official.locator('.leaflet-popup-close-button').click();
  await official.getByRole('link',{name:'Cluster review'}).click();
  await official.locator('[data-action="cluster"]').first().click();
  await official.locator('dialog[open]').waitFor();
  await official.getByLabel('Investigation notes').fill('Browser test: evidence inspected with district staff.');
  await official.getByRole('button',{name:'Start investigation'}).click();
  await official.locator('dialog .badge.investigating').waitFor();
  await official.getByLabel('Investigation notes').fill('Browser test: suspected cluster escalated for investigation.');
  await official.getByRole('button',{name:'Escalate suspected outbreak'}).click();
  await official.getByRole('button',{name:'Mark resolved'}).waitFor();
  await official.getByLabel('Investigation notes').fill('Browser test: response completed.');
  await official.getByRole('button',{name:'Mark resolved'}).click();
  await official.locator('dialog .badge.resolved').waitFor();
  await official.getByRole('button',{name:'Close details'}).click();

  await official.getByRole('link',{name:'All reports',exact:true}).click();
  await official.getByRole('button',{name:'Show tips'}).click();
  await official.locator('tbody .table-link').first().click();
  await official.getByLabel('Review notes').fill('Browser test: confirmed the tip with a volunteer.');
  await official.getByRole('button',{name:'Verify report'}).click();
  await official.locator('dialog .badge.verified').waitFor();
  await official.getByRole('button',{name:'Close details'}).click();
  await official.getByRole('combobox',{name:'Filter report status'}).selectOption('');
  await official.getByRole('searchbox',{name:'Search reports'}).fill('Ablekuma');
  assert((await official.locator('tbody tr').count())>0);
  await official.getByRole('combobox',{name:'Filter symptom category'}).selectOption('Skin rash');
  const matchingRows=await official.locator('tbody tr').allTextContents();
  assert(matchingRows.every(text=>text.includes('Skin rash')&&text.includes('Ablekuma')));
  await official.getByRole('searchbox',{name:'Search reports'}).fill('No such locality');
  await official.getByText('No reports to show',{exact:true}).waitFor();

  await official.getByRole('link',{name:'Advisories',exact:true}).click();
  await official.getByRole('button',{name:'New advisory'}).click();
  await official.getByLabel('Title',{exact:true}).fill('Browser acceptance notice');
  await official.getByLabel('Advisory message').fill('Sample message. <script>window.unwanted=true</script>');
  await official.getByRole('button',{name:'Publish advisory'}).click();
  await official.getByRole('heading',{name:'Browser acceptance notice'}).waitFor();
  assert.equal(await official.evaluate(()=>window.unwanted),undefined);
  await official.getByRole('link',{name:'Detection rules'}).click();
  await official.getByLabel('Minimum case count').fill('5');
  await official.getByLabel('Window length in days').fill('3');
  await official.getByLabel('Reason for this change').fill('Browser test: keep the illustrative default.');
  await official.getByRole('button',{name:'Save detection rules'}).click();
  await official.getByText('Detection rules updated.',{exact:true}).waitFor();
  await official.getByRole('link',{name:'Analytics',exact:true}).click();
  await official.getByRole('heading',{name:'Surveillance analytics'}).waitFor();
  assert.equal(await official.locator('.chart svg').count(),1);
  await official.screenshot({path:path.join(output,'desktop-analytics.png'),fullPage:true});
  await noOverflow(official,'Desktop analytics');

  const volunteer=await login('chv');
  assert.equal(await volunteer.getByRole('link',{name:'Detection rules'}).count(),0);
  await volunteer.getByLabel('Locality',{exact:true}).selectOption('3');
  await volunteer.getByLabel('Symptom category',{exact:true}).selectOption('Skin rash');
  await volunteer.getByLabel('Number of people affected').fill('2');
  await volunteer.getByLabel('Additional observations').fill('Browser test: fictional encounter, no patient identity.');
  await volunteer.reload();
  await volunteer.getByText('Draft restored on this device',{exact:true}).waitFor();
  assert.equal(await volunteer.getByLabel('Number of people affected').inputValue(),'2');
  await volunteer.getByRole('button',{name:'Submit case report',exact:true}).click();
  await volunteer.getByRole('heading',{name:'Case report submitted.'}).waitFor();
  await volunteer.getByRole('link',{name:'View history'}).click();
  await volunteer.locator('tbody .table-link').first().click();
  assert.equal(await volunteer.getByRole('button',{name:'Verify report'}).count(),0);
  await volunteer.getByRole('button',{name:'Close details'}).click();
  const firstTotal=await volunteer.evaluate(async()=>{const d=await(await fetch('/api/state')).json();return d.reports.length});
  await volunteer.locator('.nav').getByRole('link',{name:'New case report',exact:true}).click();
  await volunteer.getByLabel('Locality',{exact:true}).selectOption('7');
  await volunteer.getByLabel('Symptom category',{exact:true}).selectOption('Other symptoms');
  await volunteer.getByRole('button',{name:'Submit case report',exact:true}).click();
  await volunteer.getByRole('heading',{name:'Case report submitted.'}).waitFor();
  const secondTotal=await volunteer.evaluate(async()=>{const d=await(await fetch('/api/state')).json();return d.reports.length});
  assert.equal(secondTotal,firstTotal+1,'A second encounter must create its own record.');
  const ownOnly=await volunteer.evaluate(async()=>{const d=await(await fetch('/api/state')).json();return d.reports.every(r=>r.submitted_by===d.user.id)});
  assert(ownOnly);

  const clinic=await login('clinic');
  await clinic.getByLabel('Locality',{exact:true}).selectOption('4');
  await clinic.getByLabel('Symptom category',{exact:true}).selectOption('Other symptoms');
  await clinic.getByRole('button',{name:'Submit case report',exact:true}).click();
  await clinic.getByRole('heading',{name:'Case report submitted.'}).waitFor();

  const resident=await login('resident',{width:390,height:844});
  await noOverflow(resident,'Mobile resident portal');
  await resident.screenshot({path:path.join(output,'mobile-resident.png'),fullPage:true});
  await resident.getByLabel('Locality',{exact:true}).selectOption('8');
  await resident.getByLabel('Symptom category',{exact:true}).selectOption('Other symptoms');
  await resident.getByRole('button',{name:'Send community tip'}).click();
  await resident.getByRole('heading',{name:'Your tip is with the district team.'}).waitFor();
  await resident.getByRole('link',{name:'View history'}).click();
  await resident.locator('tbody .badge.unverified').first().waitFor();
  await resident.getByRole('button',{name:'Toggle navigation'}).click();
  await resident.getByRole('link',{name:'Advisories',exact:true}).click();
  await resident.getByRole('heading',{name:'Browser acceptance notice'}).waitFor();
  await noOverflow(resident,'Mobile advisories');

  const mobile=await login('official',{width:390,height:844});
  await noOverflow(mobile,'Mobile overview');
  await mobile.screenshot({path:path.join(output,'mobile-overview.png'),fullPage:true});
  await mobile.getByRole('button',{name:'Toggle navigation'}).click();
  await mobile.getByRole('link',{name:'Cluster review'}).click();
  await mobile.locator('[data-action="cluster"]').first().click();
  await noOverflow(mobile,'Mobile cluster dialog');
  await mobile.screenshot({path:path.join(output,'mobile-review.png'),fullPage:true});
  await mobile.keyboard.press('Escape');
  assert.equal(await mobile.locator('dialog[open]').count(),0);
  assert.deepEqual(errors,[],'Unexpected browser script errors');
  await browser.close();
  console.log('PASS: four roles, reporting, draft recovery, review, escalation, resolution, tip verification, notices, filters, analytics, mobile layouts, and keyboard dialog closure.');
})().catch(error=>{console.error(error);process.exit(1)});

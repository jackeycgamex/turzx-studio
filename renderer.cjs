// Renders only our own local display page. Never reads an existing browser session.
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

function getPlaywright() {
  try { return require('playwright'); } catch {}
  const bundled = path.join(os.homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright');
  if (fs.existsSync(bundled)) return require(bundled);
  throw new Error('Playwright not found. Run npm install in this project.');
}

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:8765';
  if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error('Renderer only allows localhost.');
  const token = process.env.TURZX_RENDER_TOKEN;
  if (!token) throw new Error('Renderer must be started by server.py.');
  const {chromium} = getPlaywright();
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let finishing = false;
  const finish = async () => {
    if (finishing) return;
    finishing = true;
    await browser.close();
  };
  process.once('SIGTERM', () => finish().finally(()=>process.exit(0)));
  process.once('SIGINT', () => finish().finally(()=>process.exit(0)));
  try {
    const page = await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
    let pageError = null;
    page.on('pageerror', err => { pageError=err; console.error('PAGE ERROR', err.message); });
    await page.goto(base+'/display.html?renderer=1', {waitUntil:'domcontentloaded',timeout:20000});
    await page.waitForFunction(()=>window.renderReady===true,{},{timeout:20000});
    await page.evaluate(()=>document.fonts.ready);
    let dimensions = '1280x720';
    while (!finishing) {
      const started = performance.now();
      const response = await fetch(base+'/api/state', {signal:AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('State endpoint failed');
      const state = await response.json();
      if (!state.streaming) break;
      const metrics = await (await fetch(base+'/api/metrics', {signal:AbortSignal.timeout(5000)})).json();
      const landscape = state.rotation===90 || state.rotation===270;
      const size = landscape ? {width:1280,height:720} : {width:720,height:1280};
      const nextDimensions = size.width+'x'+size.height;
      if (nextDimensions!==dimensions) {
        await page.setViewportSize(size);
        dimensions=nextDimensions;
      }
      const renderStarted=performance.now();
      const canvasData = await page.evaluate(async ({state,metrics,canvasAllowed})=>{
        if(typeof window.renderFrame==='function') await window.renderFrame(state,metrics);
        if(canvasAllowed&&state.page==='ambient'&&typeof window.captureAnimationFrame==='function') return window.captureAnimationFrame();
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        return null;
      },{state,metrics,canvasAllowed:process.env.TURZX_CAPTURE_MODE!=='screenshot'});
      if(pageError) throw new Error('Page render failed: '+pageError.message);
      const frame = canvasData ? Buffer.from(canvasData.split(',')[1],'base64') : await page.screenshot({type:'png',animations:'allow',timeout:10000});
      const renderMs=(performance.now()-renderStarted).toFixed(2);
      const ack = await fetch(base+'/api/frame', {
        method:'POST', headers:{'Content-Type':'image/png','X-Renderer-Token':token,'X-Frame-Rotation':String(state.rotation),'X-Frame-Render-Ms':renderMs,'X-Frame-Capture':canvasData?'canvas':'screenshot'},
        body:frame, signal:AbortSignal.timeout(10000)
      });
      const ackBody = await ack.text(); // Release the response body on every frame.
      if (ack.status===409) break; // A stopped session is normal cancellation.
      if (!ack.ok) throw new Error(`Frame rejected: ${ackBody}`);
      const rest = Math.max(0,1000/state.fps-(performance.now()-started));
      await new Promise(resolve=>setTimeout(resolve,rest));
    }
  } finally {
    await finish();
  }
}
main().catch(error=>{ console.error(new Date().toISOString(),error.stack||error);process.exitCode=1; });

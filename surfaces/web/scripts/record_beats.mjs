// Record the demo video's on-screen beats as silent 1080p clips of the public link, so the
// video is narration and editing only (docs/demo-script.md). Headless Chrome is driven over
// its DevTools protocol; its screencast frames become a 30 fps MP4 with ffmpeg. The live-ask
// beat sends one real question to the live API.
//   node --experimental-websocket surfaces/web/scripts/record_beats.mjs <base url> <out dir> [beat ...]
import { spawn, spawnSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';

const [base, out, ...only] = process.argv.slice(2);
const outDir = resolve(out);  // ffmpeg's concat list resolves frame paths against its own folder
mkdirSync(outDir, { recursive: true });
// On a desktop screen each route fits the viewport and long content scrolls inside its panel,
// so scrollBy names the panel it scrolls (`in`); without one it scrolls the page.
const BEATS = {
  '01-fan-68': [{ go: '#/fan?t=67:48&lang=es' }, { wait: 1500 }, { click: '.play-button' }, { wait: 13500 },
    { click: '.play-button' }, { wait: 1200 }, { clickText: 'Toda la evidencia' }, { wait: 800 },
    { scrollBy: 260, over: 1500, in: '.fan-now' }, { wait: 4500 }],
  '02-investigation': [{ go: '#/analyst?t=68:00&lang=en' }, { wait: 2500 }, { scrollTo: '.specialist-columns' },
    { wait: 3500 }, { scrollBy: 700, over: 4000, in: '.case-body' }, { wait: 1500 }, { scrollTo: '.cross-examinations' }, { wait: 3000 },
    { scrollBy: 600, over: 3000, in: '.case-body' }, { wait: 2500 }],
  '03-correction': [{ go: '#/fan?t=69:52&lang=es' }, { wait: 1200 }, { click: '#rail-tab-earlier' }, { click: '.play-button' }, { wait: 9500 },
    { click: '.play-button' }, { wait: 4500 }, { hash: '#/broadcast?t=70:30&lang=es', settle: 2500 },
    { clickText: 'Aprobar' }, { wait: 2500 }, { click: 'a[href="#/overlay"]' }, { wait: 5000 }],
  '04-followup-83': [{ go: '#/fan?t=82:50&lang=es' }, { wait: 1200 }, { click: '.play-button' }, { wait: 11500 },
    { click: '.play-button' }, { wait: 4500 }],
  '05-live-ask': [{ go: '#/fan?t=76:00&lang=es' }, { wait: 1500 }, { scrollTo: '.ask-panel' }, { wait: 1200 },
    { type: '.ask-form input', text: '¿Se está quedando sin fuerzas Ambrel?' }, { wait: 700 }, { submit: '.ask-form input' },
    { until: '!!document.querySelector(".ask-panel .recorded-answer") || !!document.querySelector(".ask-panel .unknown-question")', timeout: 90000 },
    { wait: 800 }, { scrollTo: '.live-progress' }, { wait: 5500 }],
  '06-scoreboard': [{ go: '#/analyst?t=68:00&lang=en' }, { wait: 2000 }, { click: '#tab-evaluation' }, { wait: 1500 },
    { scrollTo: '#sb-questions' }, { wait: 6000 }, { scrollBy: 500, over: 3500, in: '.case-body' }, { wait: 2000 }],
};

for (const [name, steps] of Object.entries(BEATS)) {
  if (!only.length || only.includes(name)) await record(join(outDir, `${name}.mp4`), steps);
}

async function record(out, steps) {
  const frames = join(outDir, `.frames-${Date.now()}`);
  mkdirSync(frames, { recursive: true });
  const port = 9336;
  const chrome = spawn('google-chrome', ['--headless=new', '--disable-gpu', '--no-sandbox', `--remote-debugging-port=${port}`,
    `--user-data-dir=${frames}/profile`, '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json(); } catch {}
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  let id = 0; const pending = new Map(); const shots = [];
  const send = (method, params = {}) => new Promise(r => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Page.screencastFrame') {
      const name = join(frames, `f${String(shots.length).padStart(6, '0')}.jpg`);
      writeFileSync(name, Buffer.from(m.params.data, 'base64'));
      shots.push({ name, t: m.params.metadata.timestamp });
      send('Page.screencastFrameAck', { sessionId: m.params.sessionId });
    }
  });
  const evaluate = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
  await send('Page.enable');
  // A fresh profile would show the tour's first-visit invitation in every clip.
  await send('Page.addScriptToEvaluateOnNewDocument', { source: "try { localStorage.setItem('proofline.tour', 'seen'); } catch {}" });
  await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });

  let recording = false;
  async function startScreencast() {
    if (recording) return;
    recording = true;
    await send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  }
  for (const step of steps) {
    if (step.go) { await send('Page.navigate', { url: `${base}/${step.go}` }); await sleep(step.settle ?? 5000); await startScreencast(); }
    else if (step.wait) await sleep(step.wait);
    else if (step.click) await evaluate(`document.querySelector(${JSON.stringify(step.click)})?.click()`);
    else if (step.clickText) await evaluate(`(() => { const t = ${JSON.stringify(step.clickText)};
      const el = [...document.querySelectorAll('button, summary, a, [role=tab]')].find(e => e.textContent.trim().startsWith(t));
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' }); el?.click(); return !!el; })()`);
    else if (step.type) {
      for (let i = 1; i <= step.text.length; i++) {
        await evaluate(`(() => { const input = document.querySelector(${JSON.stringify(step.type)});
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(step.text)}.slice(0, ${i}));
          input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
        await sleep(step.delay ?? 55);
      }
    }
    else if (step.submit) await evaluate(`document.querySelector(${JSON.stringify(step.submit)})?.closest('form').requestSubmit()`);
    else if (step.scrollTo) { await evaluate(`document.querySelector(${JSON.stringify(step.scrollTo)})?.scrollIntoView({ block: ${JSON.stringify(step.block ?? 'start')}, behavior: 'smooth' })`); await sleep(900); }
    else if (step.scrollBy) {
      const n = Math.max(1, Math.round((step.over ?? 2000) / 40));
      const target = step.in ? `document.querySelector(${JSON.stringify(step.in)})` : 'window';
      for (let i = 0; i < n; i++) { await evaluate(`${target}?.scrollBy(0, ${step.scrollBy / n})`); await sleep(40); }
    }
    else if (step.until) {
      const end = Date.now() + (step.timeout ?? 60000);
      while (Date.now() < end && !(await evaluate(step.until))) await sleep(500);
    }
    else if (step.hash) { await evaluate(`location.hash = ${JSON.stringify(step.hash)}`); await sleep(step.settle ?? 1500); }
  }
  await sleep(300);
  const stopped = Date.now() / 1000;  // the screencast sends frames only on change: hold the last until now
  await send('Page.stopScreencast');
  ws.close(); chrome.kill();
  await sleep(1000);  // let this Chrome release its port before the next beat's

  // Each frame lasts until the next one; the last holds until recording stopped.
  const end = Math.max(stopped, shots.at(-1).t + 0.5);
  const list = shots.map((s, i) => `file '${s.name}'\nduration ${((shots[i + 1]?.t ?? end) - s.t).toFixed(3)}`).join('\n')
    + `\nfile '${shots.at(-1).name}'\n`;
  writeFileSync(join(frames, 'list.txt'), list);
  const ff = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(frames, 'list.txt'),
    '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p',
    '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', out], { stdio: 'inherit' });
  rmSync(frames, { recursive: true, force: true });
  console.log(`${out}: ${shots.length} frames, ${(end - shots[0].t).toFixed(1)} s, ffmpeg ${ff.status}`);
}

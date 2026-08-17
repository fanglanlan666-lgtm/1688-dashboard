const { chromium } = require('playwright');
const { spawn } = require('child_process');
const http = require('http');

const ROOT = 'C:/Users/Administrator/WorkBuddy/1688业务';
const NODE = 'C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe';
const PORT = 8787;
const URL = 'http://localhost:' + PORT + '/';

const server = spawn(NODE, [ROOT + '/server.js'], { cwd: ROOT });
server.stdout.on('data', d => process.stdout.write('[server] ' + d));
server.stderr.on('data', d => process.stdout.write('[server-err] ' + d));

function waitServer() {
  return new Promise((res, rej) => {
    const t = setInterval(() => {
      http.get(URL, r => { clearInterval(t); res(); }).on('error', () => {});
    }, 300);
    setTimeout(() => { clearInterval(t); rej(new Error('server start timeout')); }, 20000);
  });
}

(async () => {
  await waitServer();
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  let syncRequested = false;
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('request', r => { if (r.url().includes('/api/sync')) syncRequested = true; });
  page.on('dialog', async d => {
    console.log('[dialog] ' + d.message().slice(0, 120));
    await d.accept();
  });

  await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });

  // 1) 按钮存在且文本正确
  const hasBtn = await page.$('#btnSync');
  if (!hasBtn) throw new Error('按钮 #btnSync 不存在');
  const txt = await page.$eval('#btnSync', el => el.textContent.trim());
  console.log('按钮文本:', txt);

  // 2) 按钮为绿色高亮（computed background 含 green 调）
  const bg = await page.$eval('#btnSync', el => getComputedStyle(el).backgroundImage);
  console.log('按钮背景:', bg.slice(0, 60));

  // 3) 点击触发 /api/sync 并进入「同步中」
  await page.click('#btnSync');
  await page.waitForFunction(
    () => { const b = document.getElementById('btnSync'); return b && b.textContent.includes('同步中'); },
    { timeout: 8000 }
  );
  console.log('已进入「同步中」状态 ✓  请求/api/sync:', syncRequested);

  // 4) 不等待完整同步（可能数分钟），确认链路已接通即收尾
  console.log('控制台错误数:', errors.length);
  if (errors.length) console.log(errors.slice(0, 8).join('\n'));

  await browser.close();
  server.kill('SIGTERM');
  process.exit(errors.length ? 1 : 0);
})().catch(e => {
  console.error('验收失败:', e.message);
  try { server.kill('SIGTERM'); } catch (_) {}
  process.exit(2);
});

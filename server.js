#!/usr/bin/env node
'use strict';
/*
 * 1688 数字营销工作台 · 本地联动服务
 * ---------------------------------------------------------------
 * 作用：
 *   1) 静态托管本目录的看板（1688数字营销工作台.html / data.js / targets.js / images/）
 *   2) 提供 POST /api/sync 接口：调用本机已登录的 lark-cli（经 sync_feishu.py）
 *      从飞书多维表拉取最新数据并覆盖写入 data.js
 *   3) 启动后自动打开浏览器到 http://localhost:8787
 *
 * 依赖：仅 Node 内置模块，零 npm 依赖。
 * 凭证：复用本机 lark-cli 的已登录会话，前端不接触任何 token。
 * 使用：双击「启动看板.bat」即可。点看板顶部「数据更新」按钮触发 /api/sync。
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { exec } = require('child_process');

const ROOT = __dirname;
const PORT = 8787;
// 本机 managed python（用于跑 sync_feishu.py）
const PY = 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe';
// sync_feishu.py 依赖 openpyxl，隔离装在 .pypkgs
const PY_PATH = 'C:\\Users\\Administrator\\WorkBuddy\\1688业务\\.pypkgs';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
  '.ico': 'image/x-icon',
  '.csv': 'text/csv; charset=utf-8'
};

// 读取同目录 .env（本地同步凭证），不依赖任何 npm 包
function loadDotEnv(file) {
  const out = {};
  try {
    const txt = fs.readFileSync(file, 'utf8');
    for (const line of txt.split(/\r?\n/)) {
      const m = line.match(/^\s*([\w.-]+)\s*=\s*(.*)\s*$/);
      if (!m) continue;            // 跳过注释/空行
      let v = m[2];
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      out[m[1]] = v;
    }
  } catch (e) { /* 无 .env 时忽略，回退 lark-cli 模式 */ }
  return out;
}

let syncing = false;

function handleSync(res) {
  if (syncing) {
    res.writeHead(409, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(JSON.stringify({ ok: false, msg: '同步进行中，请稍候…' }));
  }
  syncing = true;
  // 每次同步都重新读取 .env，便于用户填入密钥后无需重启即可生效；
  // 仅把 FEISHU_* 透传给 sync_feishu.py（有则走云端 API 模式，无则回退 lark-cli）
  const env = Object.assign({}, process.env, loadDotEnv(path.join(ROOT, '.env')), { PYTHONPATH: PY_PATH });
  const p = spawn(PY, ['sync_feishu.py'], { cwd: ROOT, env: env, windowsHide: true });
  let out = '', err = '';
  p.stdout.on('data', d => { out += d; });
  p.stderr.on('data', d => { err += d; });
  p.on('error', e => {
    syncing = false;
    res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: false, msg: '无法启动同步进程：' + e.message }));
  });
  p.on('close', code => {
    syncing = false;
    const log = (code === 0 ? out : (err || out)).slice(-1500);
    if (code === 0) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, msg: '已从飞书多维表拉取最新数据并刷新本地 data.js', log: log }));
    } else {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, msg: '同步失败（退出码 ' + code + '），详见日志', log: log }));
    }
  });
}

const server = http.createServer((req, res) => {
  const u = (req.url || '/').split('?')[0];
  if (u === '/api/sync' && req.method === 'POST') {
    return handleSync(res);
  }
  if (u === '/api/sync' && req.method === 'GET') {
    // 前端页面加载时探测本地服务是否就绪（不触发同步）
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(JSON.stringify({ ok: true, ready: true, msg: '本地同步服务就绪' }));
  }
  if (u.startsWith('/api/')) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('not found');
  }
  let rel = decodeURIComponent(u);
  if (rel === '/' || rel === '/index.html') rel = '/1688数字营销工作台.html';
  // 浏览器默认会请求 favicon.ico，本地服务没有图标时返回 204，避免控制台 404
  if (rel === '/favicon.ico') {
    res.writeHead(204);
    return res.end();
  }
  const filePath = path.normalize(path.join(ROOT, rel));
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('forbidden');
  }
  fs.readFile(filePath, (e, data) => {
    if (e) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('404 not found: ' + rel);
    }
    const ext = path.extname(filePath).toLowerCase();
    const headers = { 'Content-Type': MIME[ext] || 'application/octet-stream' };
    // data.js / targets.js 禁止缓存，确保点「数据更新」后能立即看到新数据
    if (ext === '.js' && /(^|[\\/])(data|targets)\.js$/.test(rel)) {
      headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    }
    res.writeHead(200, headers);
    res.end(data);
  });
});

server.listen(PORT, () => {
  const url = 'http://localhost:' + PORT;
  console.log('[1688看板] 本地服务已启动 -> ' + url);
  console.log('[1688看板] 点看板顶部「数据更新」按钮即可从飞书拉取最新数据');
  // 自动打开浏览器（桌面环境有效；无桌面/沙箱环境静默忽略）
  const openCmd = process.platform === 'win32'
    ? 'cmd /c start "" "' + url + '"'
    : (process.platform === 'darwin' ? 'open "' + url + '"' : 'xdg-open "' + url + '"');
  exec(openCmd, openErr => {
    if (openErr) console.log('[1688看板] 自动打开浏览器失败，请手动访问 ' + url);
  });
});

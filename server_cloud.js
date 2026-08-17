#!/usr/bin/env node
'use strict';
/*
 * 1688 数字营销工作台 · 云端同步后端
 * ---------------------------------------------------------------
 * 部署在用户自有云服务器上，常驻提供：
 *   1) 静态托管看板（index.html / data.js / targets.js / images/）
 *   2) POST /api/sync  -> 用 App ID/Secret 直连飞书 OpenAPI 拉最新数据写 data.js
 *   3) GET  /api/sync  -> 健康检查（前端加载时探测，不触发同步）
 *
 * 凭证安全：
 *   FEISHU_APP_ID / FEISHU_APP_SECRET 仅存在于【本服务端】环境变量，
 *   前端（看板页面）完全不接触任何飞书密钥。
 *   若设置了 SYNC_TOKEN，前端必须在 Header `x-sync-token` 带上相同值才能触发同步，
 *   避免任意公网请求误触发同步。
 *
 * 环境变量（均可选，括号内为默认）：
 *   PORT          监听端口            (8787)
 *   STATIC_DIR    静态根目录          (本文件所在目录)
 *   PYTHON_EXEC   python 解释器       ("python3")
 *   SYNC_CMD      同步命令(空格分隔)  ("<PYTHON_EXEC> sync_feishu.py")
 *   SYNC_TOKEN    触发令牌            (空=不校验)
 *   FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BASE_URL / PYTHONPATH / DATA_OUT_DIR
 *                透传给 sync_feishu.py（DATA_OUT_DIR 默认 = STATIC_DIR）
 *
 * 启动示例：
 *   PORT=8787 STATIC_DIR=/opt/dashboard PYTHON_EXEC=python3 \
 *   FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx PYTHONPATH=/opt/dashboard/.pypkgs \
 *   SYNC_TOKEN=一段随机串 node server_cloud.js
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = process.env.STATIC_DIR || __dirname;
const PORT = parseInt(process.env.PORT || '8787', 10);
const PY = process.env.PYTHON_EXEC || 'python3';
const SYNC_TOKEN = process.env.SYNC_TOKEN || '';

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

let syncing = false;

function syncCommand() {
  if (process.env.SYNC_CMD) return process.env.SYNC_CMD.split(' ').filter(Boolean);
  return [PY, 'sync_feishu.py'];
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,x-sync-token'
  };
}

function handleSync(res) {
  if (syncing) {
    res.writeHead(409, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(JSON.stringify({ ok: false, msg: '同步进行中，请稍候…' }));
  }
  syncing = true;
  const env = Object.assign({}, process.env, {
    PYTHONPATH: process.env.PYTHONPATH || '',
    DATA_OUT_DIR: process.env.DATA_OUT_DIR || ROOT
  });
  const cmd = syncCommand();
  const executable = cmd[0];
  const args = cmd.slice(1);
  const p = spawn(executable, args, { cwd: ROOT, env: env, windowsHide: true });
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
      res.end(JSON.stringify({ ok: true, msg: '已从飞书多维表拉取最新数据并刷新 data.js', log: log }));
    } else {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, msg: '同步失败（退出码 ' + code + '），详见日志', log: log }));
    }
  });
}

const server = http.createServer((req, res) => {
  const u = (req.url || '/').split('?')[0];

  // CORS 预检
  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders());
    return res.end();
  }

  if (u === '/api/sync' && req.method === 'GET') {
    const h = Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, corsHeaders());
    res.writeHead(200, h);
    return res.end(JSON.stringify({ ok: true, ready: true, msg: '同步服务就绪' }));
  }

  if (u === '/api/sync' && req.method === 'POST') {
    if (SYNC_TOKEN && (req.headers['x-sync-token'] || '') !== SYNC_TOKEN) {
      res.writeHead(403, Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, corsHeaders()));
      return res.end(JSON.stringify({ ok: false, msg: 'SYNC_TOKEN 校验失败' }));
    }
    return handleSync(res);
  }

  if (u.startsWith('/api/')) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('not found');
  }

  let rel = decodeURIComponent(u);
  if (rel === '/' || rel === '/index.html') rel = '/index.html';
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
    const headers = Object.assign({ 'Content-Type': MIME[ext] || 'application/octet-stream' }, corsHeaders());
    // data.js / targets.js 禁止缓存，确保点「数据更新」后能立即看到新数据
    if (ext === '.js' && /(^|[\/])(data|targets)\.js$/.test(rel)) {
      headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    }
    res.writeHead(200, headers);
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log('[1688看板·云端] 同步后端已启动 -> http://0.0.0.0:' + PORT);
  console.log('[1688看板·云端] 静态根目录: ' + ROOT);
  console.log('[1688看板·云端] 飞书凭证仅取自服务端环境变量，前端不接触任何密钥');
  console.log('[1688看板·云端] 点看板顶部「数据更新」按钮即可从飞书拉取最新数据');
});

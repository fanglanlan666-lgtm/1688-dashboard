/*
 * dashboard_guard.js — 1688 看板守护进程
 * 常驻运行，自动拉起并保活 server.js；server 崩溃后 3 秒重启，
 * 端口被占用时自动探测、空闲后立刻接管。所有事件落盘到 server_guard.log。
 *
 * 启动：node dashboard_guard.js   （建议用后台任务 / 启动看板.bat 拉起）
 */
const { spawn } = require('child_process');
const net = require('net');
const fs = require('fs');
const path = require('path');

const ROOT = 'C:/Users/Administrator/WorkBuddy/1688业务';
const NODE = 'C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe';
const SERVER = path.join(ROOT, 'server.js');
const PORT = 8787;
const LOG = path.join(ROOT, 'server_guard.log');

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(LOG, line); } catch (e) {}
  console.log(line.trim());
}

let child = null;
let restartTimer = null;

function portFree(cb) {
  const s = net.connect(PORT, '127.0.0.1');
  s.setTimeout(1500);
  s.once('connect', () => { s.destroy(); cb(false); });      // 端口被占用
  s.once('timeout', () => { s.destroy(); cb(true); });        // 连不上=空闲
  s.once('error', () => { s.destroy(); cb(true); });          // 报错=空闲
}

function startServer() {
  if (child) return;
  log('启动 server.js ...');
  child = spawn(NODE, [SERVER], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', d => fs.appendFileSync(LOG, d.toString()));
  child.stderr.on('data', d => fs.appendFileSync(LOG, d.toString()));
  child.on('exit', (code, sig) => {
    log(`server.js 退出 code=${code} sig=${sig}，3 秒后重启`);
    child = null;
    restartTimer = setTimeout(tryStart, 3000);
  });
  child.on('error', err => {
    log('spawn 失败: ' + err.message);
    child = null;
    restartTimer = setTimeout(tryStart, 3000);
  });
}

function tryStart() {
  if (child) return;
  portFree(free => {
    if (free) {
      startServer();
    } else {
      // 端口被别的实例占着（可能旧进程还活着，能正常服务），轮询等待
      log('端口 ' + PORT + ' 仍被占用，5 秒后重试探测');
      setTimeout(tryStart, 5000);
    }
  });
}

// 自愈：每 60 秒确认一次 server 是否真的在监听，没响应就强制拉起
setInterval(() => {
  if (child) {
    portFree(free => {
      if (free) {
        log('检测到端口无响应，但子进程标记存活，强制重启');
        try { child.kill('SIGKILL'); } catch (e) {}
        child = null;
        setTimeout(tryStart, 1000);
      }
    });
  } else {
    tryStart();
  }
}, 60000);

log('守护进程启动，监听端口 ' + PORT);
tryStart();

// 保持父进程不退出
setInterval(() => {}, 1 << 30);

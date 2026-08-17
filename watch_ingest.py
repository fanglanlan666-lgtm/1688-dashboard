#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1688 数字营销 · 文件夹监听自动跑
监视 ./导出 文件夹，一旦检测到新的/更新的 xlsx/csv 报表，
自动调用 ingest.py 合并去重并刷新 data.js（工作台打开即是新数据）。

用法（务必用已装 openpyxl 的 venv python 运行，否则 ingest.py 会缺依赖）：
  C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe watch_ingest.py

退出：Ctrl+C
设计要点：
- 轮询 ./导出 文件夹（无需 watchdog 第三方库，跨环境稳定）
- 检测到文件变化后，要求连续 2 个轮询周期状态一致（防读到半截拷贝的 xlsx）
- 启动时会先合并一次已有文件（幂等，去重键保证不重复）
"""
import os, time, sys, subprocess

WS = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(WS, "导出")
INGEST = os.path.join(WS, "ingest.py")
POLL = 3        # 轮询间隔(秒)
WATCH_EXT = (".xlsx", ".xls", ".csv")


def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def snapshot():
    seen = {}
    if not os.path.isdir(EXPORT_DIR):
        return seen
    for f in os.listdir(EXPORT_DIR):
        if f.lower().endswith(WATCH_EXT):
            p = os.path.join(EXPORT_DIR, f)
            try:
                st = os.stat(p)
                seen[f] = (st.st_size, round(st.st_mtime, 3))
            except OSError:
                pass
    return seen


def run_ingest():
    print(f"[{ts()}] ▶ 检测到新报表，运行 ingest.py ...", flush=True)
    try:
        r = subprocess.run([sys.executable, INGEST], cwd=WS)
        if r.returncode == 0:
            print(f"[{ts()}] ✓ 合并完成，data.js 已刷新", flush=True)
        else:
            print(f"[{ts()}] ✗ ingest.py 退出码 {r.returncode}", flush=True)
    except Exception as e:
        print(f"[{ts()}] ✗ 调用失败: {e}", flush=True)


def main():
    if not os.path.isdir(EXPORT_DIR):
        os.makedirs(EXPORT_DIR, exist_ok=True)
        print(f"[{ts()}] 已创建 导出/ 文件夹：{EXPORT_DIR}")
    print(f"[{ts()}] 监听中：{EXPORT_DIR}", flush=True)
    print(f"[{ts()}] 把后台导出的报表(xlsx/csv)丢进去即可自动合并。Ctrl+C 退出。", flush=True)

    # 启动时先处理已有文件（幂等，去重键保证不重复）
    run_ingest()
    last_run = snapshot()
    prev = last_run
    while True:
        time.sleep(POLL)
        cur = snapshot()
        # 与上一轮对比，若有变化说明文件仍在写入/移动，等待稳定
        changed = False
        all_keys = set(cur.keys()) | set(prev.keys())
        for f in all_keys:
            if cur.get(f) != prev.get(f):
                changed = True
                break
        if changed:
            prev = cur
            continue
        # 状态稳定。仅当「新增文件」或「已有文件变更」时触发；
        # 纯删除文件不触发（避免无谓合并）。
        has_new = any(cur.get(f) != last_run.get(f) for f in cur)
        if has_new:
            run_ingest()
            last_run = cur
        prev = cur


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{ts()}] 已停止监听。")
        sys.exit(0)

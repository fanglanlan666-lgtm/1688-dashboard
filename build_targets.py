#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将「月度目标日拆解」CSV 转换为 targets.js（window.DASHBOARD_TARGET）。
用法：python build_targets.py [输入csv] [输出js]
默认：目标日拆解_当月.csv -> targets.js
"""
import csv, json, os, re, sys

WS = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WS, "目标日拆解_当月.csv")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WS, "targets.js")

def pct(v):
    """'29%' -> 29 (float)；'0%' -> 0；空 -> None"""
    if v is None: return None
    s = str(v).strip().replace("%", "").replace(",", "")
    if s == "" or s == "-": return None
    try: return float(s)
    except: return None

def frac(v):
    """转化率类：'0.03' -> 0.03；'1.08%' -> 0.0108；空 -> None"""
    if v is None: return None
    s = str(v).strip().replace("%", "").replace(",", "")
    if s == "" or s == "-": return None
    try:
        x = float(s)
        return x if x <= 1 else x / 100.0
    except: return None

def num(v):
    if v is None: return None
    s = str(v).strip().replace(",", "")
    if s == "" or s == "-": return None
    try: return float(s)
    except: return None

def norm_date(v):
    """'2026/08/01' -> '2026-08-01'"""
    if not v: return ""
    s = str(v).strip().replace("\\", "/")
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    for row in r:
        if not (row.get("日期") or "").strip():
            continue
        rec = {
            "date": norm_date(row.get("日期")),
            "rhythm": (row.get("营销节奏") or "").strip(),
            "year": num(row.get("年份")),
            "month": num(row.get("月份")),
            "week": (row.get("周") or "").strip(),
            "weekday": (row.get("星期") or "").strip(),
            "mdays": num(row.get("月天数")),
            "timeProgress": pct(row.get("时间进度")),
            "salesProgress": pct(row.get("销售进度")),
            "monthSalesTarget": num(row.get("月度销售额目标")),
            "monthPayTarget": num(row.get("月度到账额目标")),
            "estDayShare": pct(row.get("预估日占比")),
            "estDaySales": num(row.get("预估日销售额")),
            "estDayVisitors": num(row.get("预估日访客")),
            "estDayConv": frac(row.get("预估日转化")),
            "estDayAov": num(row.get("预估日客单")),
            "promoBudget": num(row.get("推广预算")),
            "actSales": num(row.get("实际销售额")),
            "salesRate": pct(row.get("销售额完成率")),
            "actSalesMonth": num(row.get("实际销售额当月")),
            "actDayShare": pct(row.get("实际日占比")),
            "actVisitors": num(row.get("实际访客数")),
            "visitorRate": pct(row.get("访客完成率")),
            "actConv": frac(row.get("实际转化率")),
            "convRate": pct(row.get("转化完成率")),
            "actAov": num(row.get("实际客单价")),
            "aovRate": pct(row.get("客单价完成率")),
            "actPromo": num(row.get("实际推广费")),
            "promoMatchRate": pct(row.get("推广预算匹配率")),
        }
        rows.append(rec)

rows.sort(key=lambda x: x["date"])
meta = {
    "monthSalesTarget": rows[0]["monthSalesTarget"] if rows else None,
    "monthPayTarget": rows[0]["monthPayTarget"] if rows else None,
    "mdays": rows[0]["mdays"] if rows else None,
    "year": rows[0]["year"] if rows else None,
    "month": rows[0]["month"] if rows else None,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// 月度目标日拆解（由 build_targets.py 从 目标日拆解_当月.csv 生成）\n")
    f.write("window.DASHBOARD_TARGET = " + json.dumps(rows, ensure_ascii=False) + ";\n")
    f.write("window.DASHBOARD_TARGET_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
print(f"已生成 {OUT}：{len(rows)} 天，月度销售目标={meta['monthSalesTarget']}，天数={meta['mdays']}")

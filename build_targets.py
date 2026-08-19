#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将「月度目标日拆解」转换为 targets.js（window.DASHBOARD_TARGET）。

两种数据源（通过参数切换）：
  python build_targets.py                # 默认：读本地 CSV（目标日拆解_当月.csv）
  python build_targets.py --feishu       # 从飞书多维表实时拉取（每日自动同步用）

飞书源表：Base HLOQbPqJJa4N60sVeL7cFcShnGd / 表 tblhHLxN8ssxLcXU（女童月目标日拆解）。
该表按「日期」每日更新（实际销售额/推广费/访客/转化/客单等经 lookup 自动回填），
与业务数据同 Base，复用 sync_feishu.py 的鉴权与抓取逻辑。

输出结构固定为英文键记录（date/rhythm/actSales/salesRate…），与仪表盘读取口径一致；
无论数据源是 CSV 还是飞书，最终落盘内容格式完全相同。
"""
import csv, json, os, re, sys

WS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WS, "目标日拆解_当月.csv")
OUT = os.path.join(WS, "targets.js")

# 飞书目标表
TARGET_TABLE_ID = "tblhHLxN8ssxLcXU"


# ---- 复用的清洗函数（与旧 CSV 模式一致，保证 targets.js 单位不变）----
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


# ---- 飞书模式：抓取 + 列名/单位归一 ----
# 比值 -> 百分点字符串（如 0.35 -> "35%"），供下游 pct() 还原为数值
PP_FIELDS = {"时间进度", "销售进度", "销售额完成率", "实际日占比", "访客完成率",
             "转化完成率", "客单价完成率", "推广预算匹配率"}
# 比值但旧 CSV 存纯小数（不乘100）
PLAIN_DEC_FIELDS = {"预估日占比", "预估日转化"}


def _scalar(v):
    if isinstance(v, list):
        return v[0] if v else ""
    if isinstance(v, dict):
        return str(v.get("text") or v.get("name") or v)
    return v

def _to_str(v):
    v = _scalar(v)
    if v is None: return ""
    return str(v).strip()

def _norm_feishu_date(v):
    """飞书日期字段在 API 模式下返回毫秒时间戳(int/float)，lark-cli 模式返回 'YYYY/MM/DD' 字符串。
    统一归一为 'YYYY/MM/DD'。返回 (字符串, 是否由时间戳转换而来)。"""
    import datetime
    s = _to_str(v).strip()
    if not s:
        return s, False
    # 纯数字（含小数点）= 时间戳
    if re.fullmatch(r"\d+(\.\d+)?", s):
        try:
            ts = int(float(s))
            if ts > 1e12:        # 毫秒
                pass
            elif ts > 1e9:       # 秒
                ts *= 1000
            else:
                ts = None
            if ts:
                # 飞书日期字段存的是【中国时区 UTC+8 零点】的时间戳，必须按 +8 解析，否则按 UTC 会少一天
                tz_cst = datetime.timezone(datetime.timedelta(hours=8))
                dt = datetime.datetime.fromtimestamp(ts / 1000.0, tz=tz_cst)
                return f"{dt.year}/{dt.month:02d}/{dt.day:02d}", True
        except Exception:
            pass
    return s, False

def convert_row(raw):
    """把飞书一行（中文列名或字段ID键）转成与旧 CSV 同口径的中文列 dict。"""
    out = {}
    d, _ = _norm_feishu_date(raw.get("日期"))
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", d)
    out["日期"] = f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}" if m else d

    mr = raw.get("营销节奏")
    out["营销节奏"] = " ".join(str(x) for x in mr if x) if isinstance(mr, list) else _to_str(mr)

    yr = raw.get("年份")
    out["年份"] = _to_str(yr[0]) if isinstance(yr, list) else _to_str(yr)

    for col in ["月份", "周", "星期", "月天数", "天数", "月度销售额目标", "月度到账额目标",
                "预估日销售额", "预估日访客", "预估日客单", "推广预算", "实际销售额",
                "实际销售额当月", "实际访客数", "实际客单价", "实际推广费"]:
        out[col] = _to_str(raw.get(col))

    for col in PP_FIELDS:
        s = _to_str(raw.get(col))
        try:
            out[col] = str(int(round(float(s) * 100))) + "%"
        except Exception:
            out[col] = s

    for col in PLAIN_DEC_FIELDS:
        s = _to_str(raw.get(col))
        try:
            x = float(s)
            out[col] = ("%.4f" % x).rstrip("0").rstrip(".") if x else "0"
        except Exception:
            out[col] = s

    # 实际转化率：飞书已是百分数字符串，原样保留
    out["实际转化率"] = _to_str(raw.get("实际转化率"))
    return out

def fetch_target_raw():
    """从飞书拉取目标表，返回【中文列名、CSV 同格式】的中间 dict 列表（仅当前月）。"""
    import sync_feishu as sf
    raw = sf.fetch_table(TARGET_TABLE_ID)
    if not raw:
        raise RuntimeError("飞书目标表返回空（可能无权限或表为空）")
    # lark-cli 模式键为字段ID，需映射回中文名
    if any(k.startswith("fld") for k in raw[0].keys()):
        idmap = sf.field_id_to_name(TARGET_TABLE_ID)
        raw = [{idmap.get(k, k): v for k, v in r.items()} for r in raw]
    rows = [convert_row(r) for r in raw]
    # 只保留最新一个月（目标达成按单月展示）
    def ym(s):
        mm = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s or "")
        return (mm.group(1), mm.group(2)) if mm else None
    cur = max([ym(r.get("日期", "")) for r in rows if ym(r.get("日期", ""))], default=None)
    if cur:
        rows = [r for r in rows if ym(r.get("日期", "")) == cur]
    return rows


def main(argv):
    feishu = "--feishu" in argv
    args = [a for a in argv if a != "--feishu"]
    src = args[0] if len(args) > 0 else SRC
    out = args[1] if len(args) > 1 else OUT

    if feishu:
        print(">>> 从飞书多维表拉取目标达成（表 %s）..." % TARGET_TABLE_ID)
        rows_raw = fetch_target_raw()
        print("    当前月 %d 天" % len(rows_raw))
    else:
        with open(src, encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            rows_raw = []
            for row in r:
                if not (row.get("日期") or "").strip():
                    continue
                rows_raw.append(row)

    # 中文列 -> 英文键 记录（与旧 CSV 模式完全一致）
    records = []
    for row in rows_raw:
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
        records.append(rec)

    records.sort(key=lambda x: x["date"])
    meta = {
        "monthSalesTarget": records[0]["monthSalesTarget"] if records else None,
        "monthPayTarget": records[0]["monthPayTarget"] if records else None,
        "mdays": records[0]["mdays"] if records else None,
        "year": records[0]["year"] if records else None,
        "month": records[0]["month"] if records else None,
    }
    with open(out, "w", encoding="utf-8") as f:
        f.write("// 月度目标日拆解（" + ("飞书多维表实时拉取" if feishu else "由 build_targets.py 从 目标日拆解_当月.csv 生成") + "）\n")
        f.write("window.DASHBOARD_TARGET = " + json.dumps(records, ensure_ascii=False) + ";\n")
        f.write("window.DASHBOARD_TARGET_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
    print(f"已生成 {out}：{len(records)} 天，月度销售目标={meta['monthSalesTarget']}，天数={meta['mdays']}")


if __name__ == "__main__":
    main(sys.argv[1:])

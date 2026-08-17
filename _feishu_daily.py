#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1688 数字营销 · 每日推广日报推送（飞书）

功能：
  - 从 data.js（与看板同源）读取「前一天」的推广数据；
  - 聚合 总消耗 / 广告引导成交金额 / 投产ROI / 各计划消耗 / 商品消耗 TopN；
  - 组装飞书 interactive 卡片，通过自建应用（tenant_access_token）私聊推送给指定接收人。

用法：
  python _feishu_daily.py --dry                 # 仅打印卡片 JSON，不发送
  python _feishu_daily.py --to on_xxxx      # 指定接收人 union_id 并发送
  python _feishu_daily.py --sync --to ...   # 先重跑同步刷新 data.js 再发
  python _feishu_daily.py --date 2026-08-10 ... # 指定日期（默认：前一天，回退到最近有真实数据的日）

环境变量：
  FEISHU_APP_ID / FEISHU_APP_SECRET  （发消息用，复用同步凭证）
  FEISHU_PUSH_TO                    （默认接收人 union_id，可用 --to 覆盖）
  FEISHU_BASE_URL                    （默认 https://open.feishu.cn）

说明：接收人标识默认用 union_id（跨应用稳定）；若用 open_id 需来自本应用的 token 体系，
否则会报 99992361 open_id cross app。可用 --rid-type open_id|union_id|user_id 切换。
"""
import os, sys, re, json, datetime, urllib.request, urllib.parse

WS = os.path.dirname(os.path.abspath(__file__))
DATA_JS = os.path.join(WS, "data.js")
FEISHU_BASE_URL = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/")

def load_env():
    """从脚本同目录 .env 载入飞书凭证与推送配置（仅填充尚未在环境中存在的键）。
    这样定时任务无需在命令行里明文传 Secret，也能直接 `python _feishu_daily.py` 运行。"""
    p = os.path.join(WS, ".env")
    if not os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

def tenant_token():
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise RuntimeError("未设置 FEISHU_APP_ID / FEISHU_APP_SECRET")
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_BASE_URL + "/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    if d.get("code") != 0:
        raise RuntimeError("获取 tenant_access_token 失败: %s" % d)
    return d["tenant_access_token"]

def load_rows():
    txt = open(DATA_JS, encoding="utf-8").read()
    m = re.search(r"window\.DASHBOARD_DATA\s*=\s*(\[.*?\])\s*;", txt, re.S)
    if not m:
        raise RuntimeError("data.js 中未找到 window.DASHBOARD_DATA")
    return json.loads(m.group(1))

def f(v, nd=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x is None:
        return None
    return round(x, nd)

def money(x):
    if x is None:
        return "—"
    if abs(x) >= 10000:
        return "¥%.2f万" % (x / 10000)
    return "¥%.2f" % x

def pct(x):
    if x is None:
        return "—"
    return "%.2f%%" % (x * 100)

def pick_target_date(rows, override=None):
    """返回要汇报的日期字符串。
    仅以「含商品级真实消耗」的日期为有效汇报日（飞书多维表里 08-13 起的行多为预填/预测，
    无商品明细，不应作为日报来源）。默认取前一天；若无则回退到 ≤ 前一天 的最新有数据日。"""
    real = set()
    for r in rows:
        # 有效汇报日 = 任一维度（总览/计划/商品）在该日产生了消耗，即视为有数据。
        # 商品表常晚于计划表录入，不能只认商品层，否则 8.13 这类「仅计划级有数」的日子会被误判为空。
        if r.get("date") and (r.get("cost") or 0) > 0:
            real.add(r["date"])
    dates = sorted(real) or sorted({r.get("date") for r in rows if r.get("date")})
    if not dates:
        return None
    if override:
        return override if override in dates else None
    y = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if y in real:
        return y
    cand = [d for d in dates if d <= y]
    return cand[-1] if cand else dates[-1]

def pname(r):
    """商品展示名：款号 + 标题前 10 字，缺哪个用另一个补。"""
    sku = r.get("sku"); title = r.get("title")
    if sku and title:
        return "%s %s" % (sku, title[:10])
    return sku or title or r.get("pid") or "?"

def build_report(rows, date):
    ov = [r for r in rows if r.get("dim") == "总览" and r.get("date") == date]
    pd = [r for r in rows if r.get("dim") == "商品" and r.get("date") == date]
    pl = [r for r in rows if r.get("dim") == "计划" and r.get("date") == date]
    # 核心指标优先用「商品层」聚合（项目约定：成交/ROI/PPC 由商品维度推导）；
    # 若当日仅有计划级数据（商品表尚未录入），则回退到计划层/总览层，保证日报仍有数可报。
    has_product = any((f(r.get("cost"), 2) or 0) > 0 for r in pd)
    prod_cost = sum((f(r.get("cost"), 2) or 0) for r in pd)
    prod_gmv = sum((f(r.get("gmv"), 2) or 0) for r in pd)
    plan_rows_cost = sum((f(r.get("cost"), 2) or 0) for r in pl)
    plan_rows_gmv = sum((f(r.get("gmv"), 2) or 0) for r in pl)
    ov_cost = sum((f(r.get("cost"), 2) or 0) for r in ov)
    ov_gmv = sum((f(r.get("gmv"), 2) or 0) for r in ov)
    cost = prod_cost or plan_rows_cost or ov_cost
    gmv = prod_gmv or plan_rows_gmv or ov_gmv
    roi = round(gmv / cost, 2) if cost else None
    # 点击/展现/订单：商品层无这些字段，只能取自总览表（平台级指标，与 cost 聚合无冲突）
    imp = sum((f(r.get("imp"), 0) or 0) for r in ov)
    clk = sum((f(r.get("clk"), 0) or 0) for r in ov)
    ordn = sum((f(r.get("ord"), 0) or 0) for r in ov)
    # 商品 Top（按消耗，仅当日有商品数据时）
    pd_sorted = sorted(pd, key=lambda r: (f(r.get("cost"), 2) or 0), reverse=True)
    top = pd_sorted[:5] if has_product else []
    # 计划消耗/成交：有商品层时由商品层聚合（与总消耗自洽），否则直接用计划层原始值
    plan_cost, plan_gmv = {}, {}
    src = pd if has_product else pl
    for r in src:
        p = r.get("plan") or "未命名"
        plan_cost[p] = plan_cost.get(p, 0) + (f(r.get("cost"), 2) or 0)
        plan_gmv[p] = plan_gmv.get(p, 0) + (f(r.get("gmv"), 2) or 0)
    # ===== 推广商品分析 =====
    # 逐商品按 cost>0 分类：高效(ROI≥2 且有成交) / 零成交(消耗>0 但成交=0) / 低ROI(有成交但<1)
    efficient, waste, lowroi = [], [], []
    for r in pd:
        c = f(r.get("cost"), 2) or 0
        g = f(r.get("gmv"), 2) or 0
        if c <= 0:
            continue
        rr = (g / c) if c else None
        if g > 0 and rr is not None and rr >= 2:
            efficient.append((rr, g, c, r))
        elif g == 0:
            waste.append((c, r))
        elif rr is not None and rr < 1:
            lowroi.append((rr, g, c, r))
    efficient.sort(key=lambda x: x[1], reverse=True)   # 成交高的高效品在前
    waste.sort(key=lambda x: x[0], reverse=True)        # 烧钱多的零成交品在前
    lowroi.sort(key=lambda x: x[0])                     # ROI 最低的在前
    waste_cost = sum(x[0] for x in waste)
    # 成交主力（单款占广告成交比）
    top_gmv_r, top_gmv_val, top_gmv_share = None, 0, 0
    if gmv > 0 and pd:
        top_gmv_r = max(pd, key=lambda r: (f(r.get("gmv"), 2) or 0))
        top_gmv_val = f(top_gmv_r.get("gmv"), 2) or 0
        top_gmv_share = (top_gmv_val / gmv) if gmv else 0
    return {
        "date": date, "cost": cost, "gmv": gmv, "roi": roi,
        "imp": imp, "clk": clk, "ord": ordn,
        "top": top, "plan_cost": plan_cost, "plan_gmv": plan_gmv,
        "has_product": has_product,
        "pa": {
            "efficient": efficient, "waste": waste, "lowroi": lowroi,
            "waste_cost": waste_cost, "top_gmv_r": top_gmv_r,
            "top_gmv_val": top_gmv_val, "top_gmv_share": top_gmv_share,
        },
    }

def build_card(rep):
    d = rep["date"]
    roi = rep["roi"]
    roi_txt = "待录入" if not rep.get("has_product") else (("%.2f" % roi) if roi is not None else "—")
    # 若汇报日不是「前一天」，说明近几日数据源暂无真实投放数据，提示口径避免误解
    y = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    dnote = ""
    if d != y:
        dnote = "\n> ⚠️ %s 在数据源暂无真实投放数据，以下为最近有数据日 **%s**" % (y, d)
    # AI 小结（简单规则）
    tips = []
    if not rep.get("has_product") and rep["cost"] > 0:
        tips.append("当日仅计划级数据（消耗 %s），商品成交明细待录入，ROI 暂无法计算；商品表补录后次日推送将自动体现。" % money(rep["cost"]))
    elif roi is None:
        tips.append("昨日无广告消耗，关注计划是否在线投放。")
    elif roi >= 2:
        tips.append("投产健康（ROI %.2f ≥ 2），可适度加预算扩量。" % roi)
    elif roi >= 1:
        tips.append("投产在盈亏线上（ROI %.2f），建议优化素材/定向提升转化。" % roi)
    else:
        tips.append("投产偏低（ROI %.2f < 1），建议压缩无效消耗、复盘选品。" % roi)
    if rep["cost"] == 0:
        tips.append("昨日消耗为 0，可能无投放或数据未回传。")
    summary = " ".join(tips)

    fields = [
        {"is_short": True, "text": {"tag": "lark_md", "content": "**总消耗**\n%s" % money(rep["cost"])}},
        {"is_short": True, "text": {"tag": "lark_md", "content": "**广告引导成交**\n%s" % money(rep["gmv"])}},
        {"is_short": True, "text": {"tag": "lark_md", "content": "**投产ROI**\n%s" % roi_txt}},
        {"is_short": True, "text": {"tag": "lark_md", "content": "**点击/展现**\n%s / %s" % (f(rep["clk"], 0), f(rep["imp"], 0))}},
    ]
    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": "**汇报日期**：%s%s" % (d, dnote)}},
        {"tag": "hr"},
        {"tag": "div", "fields": fields},
    ]
    # 各计划消耗
    if rep["plan_cost"]:
        lines = []
        for p in sorted(rep["plan_cost"], key=lambda k: rep["plan_cost"][k], reverse=True):
            c = rep["plan_cost"][p]
            g = rep["plan_gmv"].get(p, 0)
            r = "待录入" if not rep.get("has_product") else (("%.2f" % (g / c)) if c else "—")
            lines.append("- %s：消耗 %s，成交 %s，ROI %s" % (p, money(c), money(g), r))
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**各计划消耗**\n" + "\n".join(lines)}})
    # 商品 Top（仅当日有商品级数据时展示；否则说明商品表尚未录入）
    if rep.get("has_product"):
        if rep["top"]:
            lines = []
            for i, r in enumerate(rep["top"], 1):
                name = r.get("sku") or r.get("title") or r.get("pid") or "?"
                if r.get("sku") and r.get("title"):
                    name = "%s %s" % (r.get("sku"), r.get("title")[:14])
                c = f(r.get("cost"), 2) or 0
                g = f(r.get("gmv"), 2) or 0
                r2 = ("%.2f" % (g / c)) if c else "—"
                lines.append("%d. %s｜消耗 %s｜成交 %s｜ROI %s" % (i, name, money(c), money(g), r2))
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**商品消耗 Top%d**\n" % len(rep["top"]) + "\n".join(lines)}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**商品消耗 Top**：当日仅计划级数据，商品级明细待录入，暂无单品 Top / 推广商品分析。"}})
    # 推广商品分析（新增：逐品投产诊断）
    pa = rep.get("pa") or {}
    if pa:
        bl = []
        eff = pa.get("efficient") or []
        waste = pa.get("waste") or []
        low = pa.get("lowroi") or []
        if eff:
            e = eff[0]
            bl.append("✅ 高效品 %d 款（ROI≥2），代表 **%s**（ROI %.1f，成交 %s），建议加预算扩量"
                      % (len(eff), pname(e[3]), e[0], money(e[1])))
        if waste:
            names = "、".join(pname(x[1]) for x in waste[:3])
            more = " 等" if len(waste) > 3 else ""
            bl.append("⚠️ %d 款商品消耗 %s 但**零成交**（如 %s%s），建议优化素材或暂停"
                      % (len(waste), money(pa.get("waste_cost", 0)), names, more))
        if low:
            names = "、".join(pname(x[3]) for x in low[:3])
            more = " 等" if len(low) > 3 else ""
            bl.append("🔻 %d 款商品有成交但 **ROI<1**（如 %s%s），投产偏低建议提价/收缩"
                      % (len(low), names, more))
        tg = pa.get("top_gmv_r")
        if tg and pa.get("top_gmv_share", 0) >= 0.3:
            bl.append("📌 成交主力 **%s** 单款贡献 %s（占广告成交 %.0f%%），注意集中度风险"
                      % (pname(tg), money(pa.get("top_gmv_val", 0)), pa.get("top_gmv_share", 0) * 100))
        if bl:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**推广商品分析**\n" + "\n".join(bl)}})
    # AI 小结
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**AI 小结**：%s" % summary}})
    elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "数据来源：1688 数字营销工作台（飞书多维表同步）"}]})
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "1688 数字营销 · 每日推广日报"},
        },
        "elements": elements,
    }

def send_card(rid, card, token, rid_type="union_id"):
    # 注意：open_id 是「按应用隔离」的，用连接器身份解析出的 open_id 不能被自定义应用
    # （cli_a925c22813789cb5）复用，会报 99992361 open_id cross app。
    # 因此默认用 union_id（跨应用稳定，同一用户在不同应用下一致）作为投递标识。
    url = FEISHU_BASE_URL + "/open-apis/im/v1/messages?receive_id_type=" + rid_type
    body = json.dumps({
        "receive_id": rid,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        d = {"code": e.code, "msg": e.read().decode("utf-8", "replace")[:400]}
    return d

def main():
    import argparse
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印卡片，不发送")
    ap.add_argument("--sync", action="store_true", help="先重跑同步刷新 data.js")
    ap.add_argument("--to", default=os.environ.get("FEISHU_PUSH_TO"), help="接收人 id（union_id / open_id / chat_id 等）")
    ap.add_argument("--rid-type", default=os.environ.get("FEISHU_PUSH_RID_TYPE"),
                   help="receive_id_type: union_id|open_id|user_id|chat_id（省略时按 id 前缀自动判断）")
    ap.add_argument("--date", default=None, help="指定汇报日期 YYYY-MM-DD")
    args = ap.parse_args()
    # 省略 --rid-type 时按接收人 id 前缀自动判断：
    #   oc_ -> chat_id（群聊） / ou_ -> open_id / on_ -> union_id / 其它 -> union_id
    if not args.rid_type:
        _to = args.to or ""
        if _to.startswith("oc_"):
            args.rid_type = "chat_id"
        elif _to.startswith("ou_"):
            args.rid_type = "open_id"
        elif _to.startswith("on_"):
            args.rid_type = "union_id"
        else:
            args.rid_type = "union_id"

    if args.sync:
        print("== 重跑同步 ==")
        sys.path.insert(0, WS)
        import sync_feishu
        sync_feishu.main()

    rows = load_rows()
    date = pick_target_date(rows, args.date)
    if not date:
        print("错误：data.js 中无任何日期数据", file=sys.stderr)
        sys.exit(1)
    rep = build_report(rows, date)
    card = build_card(rep)
    print("== 汇报日期：%s ==" % date)
    print("总消耗=%s 成交=%s ROI=%s 商品数=%d 计划数=%d" % (
        money(rep["cost"]), money(rep["gmv"]), rep["roi"], len(rep["top"]), len(rep["plan_cost"])))

    if args.dry:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return
    if not args.to:
        print("错误：未指定接收人（--to 或 FEISHU_PUSH_TO）", file=sys.stderr)
        sys.exit(1)
    token = tenant_token()
    d = send_card(args.to, card, token, rid_type=args.rid_type)
    if d.get("code") == 0:
        print("✅ 发送成功 -> %s=%s，message_id=%s" % (args.rid_type, args.to, d.get("data", {}).get("message_id")))
    else:
        print("❌ 发送失败:", json.dumps(d, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()

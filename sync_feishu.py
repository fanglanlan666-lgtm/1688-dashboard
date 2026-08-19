#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1688 数字营销 · 飞书多维表同步管道
直接从飞书多维表拉取「每日推广数据」，归一化后生成 data.js，
替代原先的 Excel 上传（ingest.py）。

数据来源（同一 Base：HLOQbPqJJa4N60sVeL7cFcShnGd）：
  tblxHX2jbknVxVvE  8.9汇总报表日更      -> 总览(dim=总览, plan=全部)
  tblUh5cwqhOeu5UD  8.9分计划报表日更    -> 计划(dim=计划, plan=一级产品)
  tblwXndSi35hLq8R  8.9大客商品日更      -> 商品(dim=商品, plan=大客方案)
  tblExpIMkbUNESTt  26年-气温数据        -> 天气(日平均气温/节气/周几)
  tbl2oWNcQOwLntTX  引用表-日期周数      -> 日期→周 映射

用法：
  python sync_feishu.py                # 全量拉取并生成 data.js
  python sync_feishu.py --dry          # 仅打印各表记录数，不写文件

依赖：复用同目录 ingest.py 的映射/清洗函数（HEADER_MAP/CANON/to_float/load_mapping...）
"""
import os, sys, json, time, subprocess, urllib.request, urllib.parse, datetime

WS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WS)
import ingest  # 复用映射与清洗逻辑

LARK_BIN = (os.environ.get("LARK_BIN") or
            r"C:/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/node_modules/@larksuite/cli/bin/lark-cli.exe")
BASE_TOKEN = "HLOQbPqJJa4N60sVeL7cFcShnGd"
# 输出目录：云端模式下由 DATA_OUT_DIR 指定（与静态托管目录一致），默认脚本所在目录
OUT_DIR = os.environ.get("DATA_OUT_DIR", WS)
# 飞书开放平台根地址（可经 FEISHU_BASE_URL 覆盖，便于自测/代理）
FEISHU_BASE_URL = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/")

# 每日三表 + 两张辅助表
TABLES = {
    "summary": {"id": "tblxHX2jbknVxVvE", "dim": "总览", "plan": "全部"},
    "plan":    {"id": "tblUh5cwqhOeu5UD", "dim": "计划", "plan": None},     # plan 取自「一级产品」
    "product": {"id": "tblwXndSi35hLq8R", "dim": "商品", "plan": "大客方案"},  # 强制大客方案
    "tuidian": {"id": "tbliISzmQA9JqUig", "dim": "商品", "plan": "全站推店"},  # 全站推店 商品×日期明细
    "weather": {"id": "tblExpIMkbUNESTt", "dim": None, "plan": None},
    "dateweek":{"id": "tbl2oWNcQOwLntTX", "dim": None, "plan": None},
    # 同一 Base 内的两份「到单品」日更数据源，用于优化周报/月报
    "jst":     {"id": "tblta8i67Iwyo1D8", "dim": "聚水潭", "plan": None},   # 聚水潭产品级日更（销量/毛利率/退款）
    "sygc":    {"id": "tblxLgoFJWWfHozn", "dim": "生意参谋", "plan": None}, # 生意参谋产品级日更（访客/点击/转化/加购）
}

# 在 ingest.HEADER_MAP 基础上补充飞书商品表特有列
# 注意：提交订单数 已由 ingest.HEADER_MAP 映射到 ord；这里把「广告引导交易数」单独保留为 ordAd，
# 不再覆盖 ord（避免把 提交订单数 与 广告引导交易数 混为一谈）。
EXTRA_MAP = {
    "广告引导交易数": "ordAd",     # 保留广告引导交易数（与 gmv 同族），单独成字段
    "获取优惠券数": "coupon",
}
HEADER_MAP = dict(ingest.HEADER_MAP)
HEADER_MAP.update(EXTRA_MAP)
CANON = ingest.CANON

def run_lark(args, retries=6):
    """调用 lark-cli，带重试（规避偶发的 Permission denied / 文件锁）。"""
    last = None
    for i in range(retries):
        try:
            p = subprocess.run([LARK_BIN] + args, capture_output=True, text=True, timeout=180)
            if p.returncode != 0:
                err = (p.stderr or p.stdout).strip()
                if "Permission denied" in err or "Resource temporarily unavailable" in err or "拒绝访问" in err:
                    last = err; time.sleep(3); continue
                raise RuntimeError("lark-cli failed: " + err[:300])
            return p.stdout
        except (subprocess.SubprocessError, OSError) as e:
            last = str(e)
            if i < retries - 1:
                time.sleep(3); continue
            raise
    raise RuntimeError("lark-cli 重试后仍失败（Permission denied）: " + str(last)[:200])

def fetch_table_lark(table_id):
    """分页拉取整表（lark-cli 模式，依赖本机已登录会话）。"""
    rows = []
    offset = 0
    while True:
        out = run_lark(["base", "+record-list", "--base-token", BASE_TOKEN,
                        "--table-id", table_id, "--limit", "200",
                        "--offset", str(offset), "--format", "json", "--as", "user"])
        obj = json.loads(out)
        d = obj["data"]
        names = d.get("fields") or d.get("field_id_list")
        data = d.get("data") or []
        if not data:
            break
        for vals in data:
            if isinstance(vals, list):
                rec = {names[i]: vals[i] for i in range(min(len(names), len(vals)))}
            else:
                rec = vals  # 保险：某些格式可能是 dict
            rows.append(rec)
        if not d.get("has_more"):
            break
        if len(data) < 200:
            break
        offset += 200
    return rows

def _feishu_tenant_token():
    """用 App ID/Secret 换取 tenant_access_token（云端模式，无需本机登录）。"""
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise RuntimeError("未设置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法使用云端 API 模式")
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_BASE_URL + "/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError("获取 tenant_access_token 失败: code=%s msg=%s" % (data.get("code"), data.get("msg")))
    return data["tenant_access_token"]

def _normalize_field(v):
    """把飞书 OpenAPI 返回的结构化字段值，转成与 lark-cli --as user 一致的人类可读形式。
    重点处理单选/多选/人员等对象型字段（API 返回 {text:...} / [{text:...}]），
    其余（文本/数字/日期字符串）原样透传。"""
    if isinstance(v, dict):
        if "text" in v: return v["text"]
        if "name" in v: return v["name"]
        return str(v)
    if isinstance(v, list):
        return [_normalize_field(x) for x in v]
    return v

def fetch_table_api(table_id, token):
    """分页拉取整表（飞书 OpenAPI 模式）。返回 [{字段名: 值, ...}]。"""
    rows = []
    page_token = ""
    while True:
        url = (FEISHU_BASE_URL + "/open-apis/bitable/v1/apps/%s/tables/%s/records?page_size=500"
               % (BASE_TOKEN, table_id))
        if page_token:
            url += "&page_token=" + urllib.parse.quote(page_token)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != 0:
            code = data.get("code")
            if code == 1254103:
                # 单表记录超过普通读取上限（2 万行），改用导出任务接口拉取
                return fetch_table_export(table_id, token)
            raise RuntimeError("拉取表 %s 失败: code=%s msg=%s" % (table_id, code, data.get("msg")))
        items = (data.get("data") or {}).get("items") or []
        if not items:
            break
        for it in items:
            fields = it.get("fields") or {}
            rows.append({k: _normalize_field(val) for k, val in fields.items()})
        if not (data.get("data") or {}).get("has_more"):
            break
        page_token = (data.get("data") or {}).get("page_token") or ""
        if not page_token:
            break
    return rows

def fetch_table_export(table_id, token):
    """大数据量表（超 2 万行，普通 records 接口报 1254103）走飞书 drive 导出任务接口。
    注意：导出是 drive 服务的能力（非 bitable 服务），参数结构为
    token=Base 的 app_token、type=bitable、sub_id=具体 table_id。
    下载的 CSV 解析为 {字段名: 值} 行列表，与 fetch_table_api 结构一致，下游无需改动。"""
    import time as _time, csv as _csv, io as _io
    DRIVE = FEISHU_BASE_URL + "/open-apis/drive/v1/export_tasks"
    H = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    # 1. 创建导出任务
    body = json.dumps({
        "file_extension": "csv",
        "token": BASE_TOKEN,
        "type": "bitable",
        "sub_id": table_id,
    }).encode("utf-8")
    req = urllib.request.Request(DRIVE, data=body, headers=H)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError("创建导出任务失败(表%s): code=%s msg=%s"
                           % (table_id, data.get("code"), data.get("msg")))
    ticket = (data.get("data") or {}).get("ticket")
    if not ticket:
        raise RuntimeError("创建导出任务未返回 ticket(表%s)" % table_id)
    # 2. 轮询任务状态
    # 关键：飞书导出接口返回里 data.result 是一个【对象】，不是字符串。
    #   result.job_status: 0=成功 1=失败 2=处理中；成功时 result.file_token 为下载令牌。
    #   （旧版代码误判 result=="finished" 且到顶层取 file_token，导致永远轮询超时）
    status_url = DRIVE + "/" + ticket + "?token=" + BASE_TOKEN
    file_token = None
    for _ in range(80):  # 80*3s = 240s 上限；实测 20s 内即可完成
        req = urllib.request.Request(status_url, headers=H)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != 0:
            raise RuntimeError("查询导出任务失败(表%s): code=%s msg=%s"
                               % (table_id, data.get("code"), data.get("msg")))
        d = data.get("data") or {}
        r = d.get("result")
        if isinstance(r, dict):
            job_status = r.get("job_status")
            ft = r.get("file_token")
        else:
            # 兜底：个别环境可能直接返回字符串状态
            job_status = 0 if r == "finished" else None
            ft = d.get("file_token")
        if job_status == 0 and ft:
            file_token = ft
            break
        if job_status == 1:
            raise RuntimeError("导出任务失败(表%s): %s"
                               % (table_id, (isinstance(r, dict) and r.get("job_error_msg")) or "unknown"))
        _time.sleep(3)
    if not file_token:
        raise RuntimeError("导出任务超时未完成(表%s)" % table_id)
    # 3. 下载 CSV
    # 飞书下载端点：GET /open-apis/drive/v1/export_tasks/file/{file_token}/download
    # 注意：下载路径里【不含 ticket】，只用 file_token + ?token=Base的app_token
    dl_url = DRIVE + "/file/" + file_token + "/download?token=" + BASE_TOKEN
    req = urllib.request.Request(dl_url, headers=H)
    with urllib.request.urlopen(req, timeout=120) as resp:
        csv_bytes = resp.read()
    # 4. 解析 CSV（utf-8-sig 去掉 BOM）
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = list(_csv.reader(_io.StringIO(text)))
    if not reader:
        return []
    header = reader[0]
    out = []
    ncol = len(header)
    for row in reader[1:]:
        if not row:
            continue
        if len(row) < ncol:
            row = row + [""] * (ncol - len(row))
        elif len(row) > ncol:
            row = row[:ncol]
        out.append({header[i]: row[i] for i in range(ncol)})
    return out

def fetch_table(table_id):
    """分发：有 FEISHU_APP_ID/SECRET 走云端 API；否则走本机 lark-cli。
    容错：单表拉取失败（如应用无该表权限 RolePermNotAllow）先回退 lark-cli 用户会话，
    再不行则跳过该表返回 []，绝不连累其他表同步。"""
    if os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"):
        if not getattr(fetch_table, "_token", None):
            fetch_table._token = _feishu_tenant_token()
        try:
            return fetch_table_api(table_id, fetch_table._token)
        except Exception as e:
            print(f"  ! 表 {table_id} API 拉取失败({e})，回退 lark-cli 用户会话…")
            try:
                return fetch_table_lark(table_id)
            except Exception as e2:
                print(f"  ! 表 {table_id} lark-cli 也失败({e2})，跳过该表（不阻塞其他表同步）")
                return []
    return fetch_table_lark(table_id)

def field_id_to_name(table_id):
    """返回 {field_id: 字段名}。lark-cli 模式拉取的记录以字段ID为键，
    需据此映射回中文名，才能与 build_targets.py 的中文列名对齐。"""
    if os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"):
        if not getattr(field_id_to_name, "_tok", None):
            field_id_to_name._tok = _feishu_tenant_token()
        tok = field_id_to_name._tok
        out = {}
        url = FEISHU_BASE_URL + "/open-apis/bitable/v1/apps/%s/tables/%s/fields?page_size=200" % (BASE_TOKEN, table_id)
        while True:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            if d.get("code") != 0:
                raise RuntimeError("拉字段失败(表%s): %s" % (table_id, d.get("msg")))
            for it in (d.get("data") or {}).get("items") or []:
                fid = it.get("field_id") or it.get("fieldId")
                fn = it.get("field_name") or it.get("name")
                if fid and fn:
                    out[fid] = fn
            pt = (d.get("data") or {}).get("page_token")
            if not pt or not (d.get("data") or {}).get("has_more"):
                break
            url = (FEISHU_BASE_URL + "/open-apis/bitable/v1/apps/%s/tables/%s/fields?page_size=200&page_token=%s"
                   % (BASE_TOKEN, table_id, urllib.parse.quote(pt)))
        return out
    # lark-cli 模式
    out = run_lark(["base", "+field-list", "--base-token", BASE_TOKEN, "--table-id", table_id, "--as", "user"])
    obj = json.loads(out)
    items = (obj.get("data") or {}).get("fields") or []
    return {it.get("id"): it.get("name") for it in items if it.get("id")}

def to_date(v):
    if v is None: return ""
    # 飞书「日期」类型返回毫秒时间戳，基准为【北京时间 UTC+8】（如 1785513600000 = 2026-08-01）。
    # 必须先把时间戳按 +8h 折算成北京时间再取日期，否则 utcfromtimestamp 取的是 UTC 日期，
    # 会整日偏早一天（例如 8.14 午夜北京 = 8.13 16:00 UTC，被错标成 8.13）。
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.lstrip("-").isdigit()):
        try:
            n = float(v)
            if n > 1e11:          # 毫秒时间戳
                n = n / 1000
            if 1e9 <= n <= 1e11:  # 秒时间戳
                return datetime.datetime.utcfromtimestamp(n + 8 * 3600).strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(v).strip()
    import re
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 无分隔符的 8 位日期，如 20260801（分计划报表的「统计日期」）
    m2 = re.search(r"(\d{4})(\d{2})(\d{2})", s.replace("-", "").replace("/", ""))
    if m2: return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return ""

def build_records(raw, meta):
    """把飞书记录行转换为 CANON 规范记录。"""
    dim, plan_fixed = meta["dim"], meta["plan"]
    out = []
    for r in raw:
        # 中文表头 -> 规范字段
        rec = {k: None for k in CANON}
        rec["dim"] = dim
        # 日期
        date = None
        for dk in ("日期", "统计日期"):
            if r.get(dk) not in (None, ""):
                date = to_date(r.get(dk)); break
        if not date:
            continue
        rec["date"] = date
        # plan
        if plan_fixed:
            rec["plan"] = plan_fixed
        else:
            pv = r.get("一级产品")
            if pv is None or str(pv).strip() in ("汇总", "", "全部"):
                continue  # 丢弃汇总行
            rec["plan"] = str(pv).strip()
        if dim == "商品":
            pid = r.get("商品ID")
            if pid is None or str(pid).strip() in ("汇总", "", "-"):
                continue
            rec["pid"] = str(pid).strip()
            rec["title"] = str(r.get("商品标题") or "").strip()
        elif dim == "计划":
            rec["pid"] = ""
        else:  # 总览
            rec["pid"] = ""
        # 指标（跳过已在上面单独处理的维度字段，避免 pid/title 被数值化覆盖）
        for zh, en in HEADER_MAP.items():
            if en in ("pid", "title", "sku", "date", "plan", "dim"):
                continue
            if zh in r and r[zh] is not None and str(r[zh]).strip() != "":
                rec[en] = ingest.to_float(r[zh])
        if dim == "商品":
            rec["sku"] = (MAPPING or {}).get(rec["pid"], "")
        # 派生
        if rec.get("ctr") is None and rec.get("imp") and rec.get("clk"):
            rec["ctr"] = rec["clk"] / rec["imp"]
        if rec.get("cpc") is None and rec.get("clk") and rec.get("cost"):
            rec["cpc"] = rec["cost"] / rec["clk"]
        if rec.get("roi") is None and rec.get("cost") and rec.get("gmv"):
            rec["roi"] = rec["gmv"] / rec["cost"]
        out.append(rec)
    return out

def _fv(v):
    """飞书多选字段返回 list，这里取第一个非空值。"""
    if isinstance(v, list):
        for x in v:
            if x not in (None, ""):
                return x
        return ""
    return v

def ffirst(r, keys):
    """依次尝试多个候选中文列名，返回第一个能解析成 float 的非空值。"""
    for k in keys:
        v = ingest.to_float(r.get(k))
        if v is not None:
            return v
    return None

def build_tuidian(raw):
    """全站推店 商品×日期明细(tbliISzmQA9JqUig) -> CANON 规范记录。
    该表只有「消耗量/曝光/点击/询盘/线索/成交笔数(deal)」等，无成交金额，
    故标准金额 ROI 保持 None，成交以 deal(广告引导交易数) 体现效率。"""
    out = []
    for r in raw:
        date = to_date(r.get("日期"))
        if not date:
            continue
        pid = str(r.get("商品ID") or "").strip()
        if pid in ("", "汇总", "-"):
            continue
        rec = {k: None for k in CANON}
        rec["dim"] = "商品"
        rec["plan"] = "全站推店"
        rec["date"] = date
        rec["pid"] = pid
        rec["sku"] = (MAPPING or {}).get(pid, "")
        rec["title"] = str(r.get("offer标题") or "").strip()
        rec["cost"] = ingest.to_float(r.get("消耗量"))
        rec["imp"] = ingest.to_float(r.get("曝光量"))
        rec["vexp"] = ingest.to_float(r.get("扶持曝光量"))
        rec["clk"] = ingest.to_float(r.get("点击量"))
        rec["ctr"] = ingest.to_float(r.get("点击转化率"))
        rec["ordAd"] = ingest.to_float(r.get("点击立即订购数"))
        rec["ord"] = ingest.to_float(r.get("提交订单数"))
        rec["cart"] = ingest.to_float(r.get("加购数"))
        rec["coupon"] = ingest.to_float(r.get("优惠券数"))
        rec["favP"] = ingest.to_float(r.get("收藏商品数"))
        rec["favS"] = ingest.to_float(r.get("收藏店铺数"))
        rec["inq"] = ingest.to_float(r.get("询盘量"))
        rec["inqCost"] = ingest.to_float(r.get("询盘成本"))
        rec["lead"] = ingest.to_float(r.get("线索量"))
        rec["leadCost"] = ingest.to_float(r.get("线索成本"))
        rec["deal"] = ingest.to_float(r.get("广告引导交易数"))
        # 派生比率
        if rec["ctr"] is None and rec["imp"] and rec["clk"]:
            rec["ctr"] = rec["clk"] / rec["imp"]
        if rec["cpc"] is None and rec["clk"] and rec["cost"]:
            rec["cpc"] = rec["cost"] / rec["clk"]
        out.append(rec)
    return out

def build_jst(raw):
    """聚水潭产品级日更 -> 到单品每日记录（销售额/毛利率/退款）。"""
    out = []
    for r in raw:
        d = to_date(r.get("日期"))
        if not d:
            continue
        sku = str(_fv(r.get("款式编码")) or "").strip()
        if not sku:
            continue
        out.append({
            "date": d,
            "sku": sku,
            "title": str(_fv(r.get("商品简称")) or _fv(r.get("商品名称")) or "").strip(),
            "qty": ffirst(r, ["实销数量", "销售数量"]),
            "amount": ffirst(r, ["实销金额", "销售金额"]),
            "cost": ffirst(r, ["销售成本", "实发成本"]),
            "gm": ingest.to_float(r.get("销售毛利率")),
            "retAmt": ffirst(r, ["当期实退金额", "当期退货金额"]),
            "shipAmt": ffirst(r, ["实发金额", "销售金额"]),
        })
    return out

def build_sygc(raw):
    """生意参谋产品级日更 -> 到单品每日记录（访客/点击/转化/加购）。"""
    out = []
    for r in raw:
        d = to_date(r.get("日期"))
        if not d:
            continue
        sku = str(_fv(r.get("款号")) or _fv(r.get("主款号")) or _fv(r.get("主款号 2")) or "").strip()
        if not sku:
            continue
        out.append({
            "date": d,
            "sku": sku,
            "pid": str(_fv(r.get("商品ID")) or "").strip(),
            "imp": ffirst(r, ["展现次数"]),
            "vexp": ffirst(r, ["广告展现次数"]),
            "visitors": ffirst(r, ["访客数"]),
            "clk": ffirst(r, ["广告点击次数"]),
            "cartP": ffirst(r, ["加购人数", "加购件数"]),
            "payBuyers": ffirst(r, ["支付买家数"]),
            "payAmt": ffirst(r, ["支付金额"]),
            "paidVisitorRatio": ffirst(r, ["付费访客占比"]),
            "cartRate": ffirst(r, ["加购转化率"]),
            "payConv": ffirst(r, ["支付转化率"]),
            "clickConv": ffirst(r, ["点击转化率"]),
            "favRate": ffirst(r, ["收藏转化率"]),
        })
    return out

def aggregate_jst(rows, prod_skus):
    """聚水潭明细 -> (日级全店汇总, 推广单品×月)。
    日级全店汇总用于周报/月报；单品×月仅保留在投推广单品，体积可控。
    gmW=毛利额(=毛利率×销售额)，用于全店加权毛利率。"""
    day, sku = {}, {}
    for r in rows:
        d = r.get("date")
        if not d:
            continue
        qty = r.get("qty") or 0
        amount = r.get("amount") or 0
        gm = r.get("gm")
        gmW = (gm * amount) if (gm is not None and amount) else 0
        retAmt = r.get("retAmt") or 0
        shipAmt = r.get("shipAmt") or 0
        dd = day.setdefault(d, {"qty":0, "amount":0, "gmW":0, "retAmt":0, "shipAmt":0})
        dd["qty"] += qty; dd["amount"] += amount; dd["gmW"] += gmW
        dd["retAmt"] += retAmt; dd["shipAmt"] += shipAmt
        s = r.get("sku")
        if s and s in prod_skus:
            m = d[:7]
            ss = sku.setdefault(s, {})
            mm = ss.setdefault(m, {"title": r.get("title") or "", "qty":0, "amount":0, "gmW":0, "retAmt":0, "shipAmt":0})
            mm["qty"] += qty; mm["amount"] += amount; mm["gmW"] += gmW
            mm["retAmt"] += retAmt; mm["shipAmt"] += shipAmt
    return day, sku

def aggregate_sygc(rows, prod_skus):
    """生意参谋明细 -> (日级全店汇总, 推广单品×月)。
    率指标(点击率/加购率/支付转化率/付费访客占比)改存分子分母，汇总后在前端重算，避免率被错误平均。
    paidVisW=付费访客数(=付费访客占比×访客数)。"""
    day, sku = {}, {}
    for r in rows:
        d = r.get("date")
        if not d:
            continue
        imp = r.get("imp") or 0
        vexp = r.get("vexp") or 0
        visitors = r.get("visitors") or 0
        clk = r.get("clk") or 0
        cartP = r.get("cartP") or 0
        payBuyers = r.get("payBuyers") or 0
        payAmt = r.get("payAmt") or 0
        pvr = r.get("paidVisitorRatio")
        paidVisW = (pvr * visitors) if (pvr is not None and visitors) else 0
        dd = day.setdefault(d, {"imp":0, "vexp":0, "visitors":0, "clk":0, "cartP":0, "payBuyers":0, "payAmt":0, "paidVisW":0})
        dd["imp"] += imp; dd["vexp"] += vexp; dd["visitors"] += visitors; dd["clk"] += clk
        dd["cartP"] += cartP; dd["payBuyers"] += payBuyers; dd["payAmt"] += payAmt; dd["paidVisW"] += paidVisW
        s = r.get("sku")
        if s and s in prod_skus:
            m = d[:7]
            ss = sku.setdefault(s, {})
            mm = ss.setdefault(m, {"imp":0, "vexp":0, "visitors":0, "clk":0, "cartP":0, "payBuyers":0, "payAmt":0, "paidVisW":0})
            mm["imp"] += imp; mm["vexp"] += vexp; mm["visitors"] += visitors; mm["clk"] += clk
            mm["cartP"] += cartP; mm["payBuyers"] += payBuyers; mm["payAmt"] += payAmt; mm["paidVisW"] += paidVisW
    return day, sku

def build_calendar(weather_raw, dw_raw):
    cal = {}
    weather = []   # 逐日逐区域气温明细：{date,region,city,temp,tempLow,tempHigh,solarTerm}
    # 日期周数表：日期 -> 周/星期/季度
    for r in dw_raw:
        d = to_date(r.get("日期"))
        if not d: continue
        cal.setdefault(d, {})
        cal[d]["week"] = str(_fv(r.get("周")) or "").strip()
        cal[d]["weekday"] = str(_fv(r.get("星期")) or "").strip()
        cal[d]["quarter"] = str(_fv(r.get("季度")) or "").strip()
    # 天气表：日期 -> 气温/节气/周几（temp 取多区域均值，tempLow/tempHigh 取极值，作为天气 chip 代表值）
    for r in weather_raw:
        d = to_date(r.get("日期"))
        if not d: continue
        c = cal.setdefault(d, {})
        # 区域 / 城市（区域用于前端按区域筛选气温趋势）
        region = str(_fv(r.get("区域")) or "").strip()
        city = str(_fv(r.get("城市")) or "").strip()
        # 日平均气温：区域均值
        if r.get("日平均气温") not in (None, ""):
            try:
                tv = float(r["日平均气温"])
                c["tempSum"] = (c.get("tempSum") or 0) + tv
                c["tempN"] = (c.get("tempN") or 0) + 1
            except: pass
        # 最低气温 / 最高气温：跨区域取极值
        if r.get("最低气温") not in (None, ""):
            try:
                lv = float(str(_fv(r.get("最低气温"))).replace("℃","").strip())
                c["tempLow"] = lv if c.get("tempLow") is None else min(c["tempLow"], lv)
            except: pass
        if r.get("最高气温") not in (None, ""):
            try:
                hv = float(str(_fv(r.get("最高气温"))).replace("℃","").strip())
                c["tempHigh"] = hv if c.get("tempHigh") is None else max(c["tempHigh"], hv)
            except: pass
        if r.get("节气") not in (None, ""):
            c["solarTerm"] = c.get("solarTerm") or str(_fv(r.get("节气")) or "").strip()
        if r.get("周几") not in (None, ""):
            c["weekday"] = c.get("weekday") or str(_fv(r.get("周几")) or "").strip()
        if r.get("周") not in (None, ""):
            c["week"] = c.get("week") or str(_fv(r.get("周")) or "").strip()
        # 逐区域明细（仅当能识别区域时入表，供前端筛选）
        if region:
            rec = {"date": d, "region": region, "city": city}
            if r.get("日平均气温") not in (None, ""):
                try: rec["temp"] = round(float(r["日平均气温"]), 1)
                except: rec["temp"] = None
            else:
                rec["temp"] = None
            rec["tempLow"] = c.get("tempLow") if "tempLow" in c else None
            rec["tempHigh"] = c.get("tempHigh") if "tempHigh" in c else None
            rec["solarTerm"] = c.get("solarTerm", "")
            weather.append(rec)
    # 天气 chip 代表值：temp 取多区域均值
    for d, c in cal.items():
        if c.get("tempN"):
            c["temp"] = round(c["tempSum"] / c["tempN"], 1)
        c.pop("tempSum", None); c.pop("tempN", None)
    return cal, weather

def main():
    global MAPPING
    dry = "--dry" in sys.argv
    print("== 飞书多维表同步 ==")
    MAPPING = ingest.load_mapping()  # 商品ID -> 款号
    raw = {k: fetch_table(v["id"]) for k, v in TABLES.items()}
    for k, v in raw.items():
        print(f"  {k}: {len(v)} 行")

    if dry:
        return

    merged = []
    for key in ("summary", "plan", "product"):
        if key in raw:
            recs = build_records(raw[key], TABLES[key])
            print(f"  -> {key} 规范化: {len(recs)} 条")
            merged.extend(recs)
    # 全站推店 商品×日期明细（字段名与大客商品表不同，独立解析）
    if "tuidian" in raw:
        recs = build_tuidian(raw["tuidian"])
        print(f"  -> 全站推店(tuidian) 规范化: {len(recs)} 条")
        merged.extend(recs)

    # 聚水潭 / 生意参谋：到单品日更，用于周报月报的销售额/退款/访客/转化等
    jst_rows = build_jst(raw["jst"])
    print(f"  -> 聚水潭 规范化: {len(jst_rows)} 条")
    sygc_rows = build_sygc(raw["sygc"])
    print(f"  -> 生意参谋 规范化: {len(sygc_rows)} 条")

    # 计划口径归一化
    for r in merged:
        if r.get("plan") in ingest.PLAN_ALIAS:
            r["plan"] = ingest.PLAN_ALIAS[r["plan"]]
    merged.sort(key=lambda x: (x["date"], x["dim"], x["plan"], x["pid"] or ""))

    # ===== 由商品层聚合「广告引导成交金额(gmv) / 投产ROI」到 总览(按日) 与 计划(按日+计划) =====
    # 商品表是唯一带 gmv/roi 的层级；总览/计划表缺失这两列，故由商品层汇总回填，
    # 使首页 KPI、计划对比表、周报月报均可直接读取，无需前端临时拼装。
    # ROI 口径 = 广告引导成交(gmv) / 该层级实际消耗(cost)，与商品卡 ROI 同一定义。
    prod_acc = {}  # (date, plan) -> [cost, gmv]
    for r in merged:
        # 仅聚合「有成交金额」的商品行；全站推店无 gmv，排除以避免稀释其他计划/总览 ROI
        if r.get("dim") != "商品" or not r.get("gmv"):
            continue
        k = (r.get("date"), r.get("plan"))
        acc = prod_acc.setdefault(k, [0.0, 0.0])
        acc[0] += float(r.get("cost") or 0)
        acc[1] += float(r.get("gmv") or 0)
    # 总览：按日汇总全部商品
    sum_by_date = {}
    for (date, _p), (c, g) in prod_acc.items():
        acc = sum_by_date.setdefault(date, [0.0, 0.0])
        acc[0] += c; acc[1] += g
    for r in merged:
        if r.get("dim") == "总览":
            acc = sum_by_date.get(r.get("date"))
            if acc and acc[1] > 0:
                r["gmv"] = round(acc[1], 2)
                r["roi"] = round(acc[1] / acc[0], 4) if acc[0] else None
        elif r.get("dim") == "计划":
            acc = prod_acc.get((r.get("date"), r.get("plan")))
            if acc and acc[1] > 0 and r.get("cost"):
                r["gmv"] = round(acc[1], 2)
                r["roi"] = round(acc[1] / r["cost"], 4)  # 用计划行自身 cost 作分母，口径一致

    # 关联主图（复用 产品主图.xlsx）
    img_map = ingest.load_img_map()
    if img_map:
        pid_set = set(r.get("pid") for r in merged if r.get("dim") == "商品" and r.get("pid"))
        img_paths = ingest.download_images(pid_set, img_map)
        for r in merged:
            if r.get("dim") == "商品":
                r["img"] = img_paths.get(r.get("pid"), "")
    else:
        print("  （未找到 产品主图.xlsx，商品主图不显示）")

    # 写 data.js（与 ingest 同格式）
    js_rows = []
    for r in merged:
        o = {}
        for k in CANON:
            v = r.get(k)
            if v is None or v == "": o[k] = None
            else:
                try: o[k] = float(v) if ("." in str(v) or k in ("imp","clk","cost")) else (int(v) if str(v).isdigit() else v)
                except: o[k] = v
        if o.get("pid") is not None: o["pid"] = str(o["pid"])
        if o.get("sku") is not None: o["sku"] = str(o["sku"])
        js_rows.append(o)

    # 天气/周 日历表
    cal, weather = build_calendar(raw["weather"], raw["dateweek"])
    cal_js = "window.DASHBOARD_CALENDAR = " + json.dumps(cal, ensure_ascii=False) + ";\n"
    weather_js = "window.DASHBOARD_WEATHER = " + json.dumps(weather, ensure_ascii=False) + ";\n"

    # 聚水潭 / 生意参谋：预聚合为「日级全店汇总」(周报月报用) + 「推广单品×月」(单品月表 enrich 用)
    # 不存全量日明细，避免 data.js 膨胀到数十 MB。
    prod_skus = set(r.get("sku") for r in merged if r.get("dim") == "商品" and r.get("sku"))
    jst_day, jst_sku = aggregate_jst(jst_rows, prod_skus)
    sygc_day, sygc_sku = aggregate_sygc(sygc_rows, prod_skus)
    jst_js = "window.DASHBOARD_JST_DAY = " + json.dumps(jst_day, ensure_ascii=False) + ";\n"
    sygc_js = "window.DASHBOARD_SYGC_DAY = " + json.dumps(sygc_day, ensure_ascii=False) + ";\n"
    jstsku_js = "window.DASHBOARD_JST_SKU = " + json.dumps(jst_sku, ensure_ascii=False) + ";\n"
    sygcsku_js = "window.DASHBOARD_SYGC_SKU = " + json.dumps(sygc_sku, ensure_ascii=False) + ";\n"
    print(f"  -> 聚水潭 日汇总 {len(jst_day)} 天 / 单品×月 {sum(len(v) for v in jst_sku.values())} 条")
    print(f"  -> 生意参谋 日汇总 {len(sygc_day)} 天 / 单品×月 {sum(len(v) for v in sygc_sku.values())} 条")

    # 预算配置合并
    budget_js = ""
    BUDGET_FILE = os.path.join(OUT_DIR, "budget.json")
    if os.path.exists(BUDGET_FILE):
        try:
            with open(BUDGET_FILE, encoding="utf-8") as bf:
                bcfg = json.load(bf)
            if isinstance(bcfg, dict) and (bcfg.get("total") or bcfg.get("plans")):
                budget_js = "window.DASHBOARD_BUDGET = " + json.dumps({
                    "total": float(bcfg.get("total") or 0),
                    "plans": bcfg.get("plans") or {}
                }, ensure_ascii=False) + ";\n"
        except Exception as e:
            print("  ⚠️ budget.json 读取失败:", e)

    OUT_JS = os.path.join(OUT_DIR, "data.js")
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(budget_js + cal_js + weather_js + jst_js + sygc_js + jstsku_js + sygcsku_js +
                "window.DASHBOARD_DATA = " + json.dumps(js_rows, ensure_ascii=False) + ";\n")
    print(f"完成：{len(js_rows)} 条记录 + 日历 {len(cal)} 天 + 气温 {len(weather)} 条 + 聚水潭[日{len(jst_day)}/单品{sum(len(v) for v in jst_sku.values())}] + 生意参谋[日{len(sygc_day)}/单品{sum(len(v) for v in sygc_sku.values())}] -> data.js")

if __name__ == "__main__":
    main()

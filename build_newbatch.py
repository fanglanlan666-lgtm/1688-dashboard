import pandas as pd, sys, re
sys.stdout.reconfigure(encoding='utf-8')

JT26 = r'C:\360极速浏览器下载\销售主题分析_商品_20260810155006_183907082_1.xlsx'
MASTER = '26年8.10-9.10_XQ6新款_SKC预估.xlsx'
OUT = '26年8.10-9.10_XQ6补充49款_SKC预估.xlsx'

raw = '''XQ6CS426 嫩绿 XQ6CS426 米色 XQ6CS429 绿色 XQ6CS429 粉色 XQ6CS429 黄色 XQ6DD508 黑色 XQ6DD508 深灰 XQ6DD509 咖色 XQ6DD509 粉色 XQ6DQ501 紫色 XQ6DQ501 杏色 XQ6DQ501 浅蓝 XQ6DQ501 粉色 XQ6DQ502 灰色 XQ6DQ502 暗红 XQ6DQ502 黄色 XQ6KT552 大红 XQ6KT552 奶黄 XQ6KT552 紫色 XQ6LY542 咖色 XQ6LY542 粉色 XQ6LY542 杏色 XQ6LY543 咖色 XQ6LY543 大红 XQ6MJ463 粉色 XQ6MJ463 玫紫 XQ6MJ463 黄绿 XQ6MJ465 黄色 XQ6MJ465 橘色 XQ6MJ465 浅紫 XQ6MJ466 黑色 XQ6MY445 粉色 XQ6MY445 黑色 XQ6MY445 咖色 XQ6MY445 米色 XQ6MY445 藏青 XQ6MY453 黄色 XQ6MY453 米色 XQ6NZ532 蓝色 XQ6NZ532 深蓝 XQ6NZ536 深蓝 XQ6NZ536 浅蓝 XQ6NZ537 蓝色 XQ6NZ537 藏青 XQ6NZ538 深蓝 XQ6NZ538 蓝色 XQ6QK563 粉色 XQ6QK563 黑白 XQ6SK522 粉色 XQ6SK522 酒红色 XQ6SK522 杏色 XQ6SK523 绿色 XQ6SK523 粉色 XQ6SK523 紫色 XQ6SK525 藏青 XQ6SK525 酒红 XQ6SK526 深灰 XQ6SK526 赤红 XQ6SK529 暗红 XQ6SK529 藏青 XQ6SK530 深蓝 XQ6SK572 藏青 XQ6SK572 紫红 XQ6TX402 米色 XQ6TX402 黄色 XQ6TX402 紫色 XQ6TX402 嫩绿 XQ6TX404 粉色 XQ6TX404 紫色 XQ6TX404 杏色 XQ6TX408 杏色 XQ6TX408 咖色 XQ6TX408 紫红 XQ6TX409 黄色 XQ6TX409 蓝色 XQ6TX416 白色 XQ6TX417 米色 XQ6TX418 藏青 XQ6TX418 粉条纹 XQ6TX418 黄色 XQ6TX422 浅卡其 XQ6TX422 杏色 XQ6TX422 粉色 XQ6TX430 深灰 XQ6TX430 米色 XQ6TX430 粉色 XQ6WT472 黑色 XQ6WT472 杏色 XQ6WT473 花灰 XQ6WT475 粉色 XQ6WT475 灰色 XQ6WT479 藏青 XQ6WY432 米色 XQ6WY432 红色 XQ6WY434 粉色 XQ6WY434 藏青 XQ6WY434 花灰 XQ6WY439 米色 XQ6WY439 粉色 XQ6ZK511 藏青 XQ6ZK511 咖色 XQ6ZK511 深灰 XQ6ZK513 咖色 XQ6ZK513 粉色 XQ6ZK513 暗红 XQ6ZK514 藏青 XQ6ZK514 浅灰 XQ6ZK514 暗红 XQ6ZK516 深灰 XQ6ZK516 浅粉 XQ6ZK516 紫红 XQ6ZK516 花灰 XQ6ZK517 灰色 XQ6ZK517 红色 XQ6ZK520 黑色 XQ6ZK520 粉色 XQ6ZK520 深灰 XQ6ZK566 咖色 XQ6ZK566 藏青 XQ6ZK566 红色'''

pairs = re.findall(r'(XQ6\w+)\s+([^\s]+)', raw)
style_color = {}
for code, color in pairs:
    style_color.setdefault(code, []).append(color)
# 去重同款内重复颜色（如用户录入重复）
for c in style_color:
    seen=[]; [seen.append(x) for x in style_color[c] if x not in seen]
    style_color[c]=seen
codes = list(style_color.keys())

jt = pd.read_excel(JT26)
jt['款式编码'] = jt['款式编码'].astype(str).str.strip()
for col in ['销售数量','实发金额','实退金额','实发数量','实退数量','支付金额','支付商品件数']:
    if col in jt.columns:
        jt[col] = pd.to_numeric(jt[col], errors='coerce')

# R_cat 复用主表
rc = pd.read_excel(MASTER, sheet_name='各类目R倍数', header=0)
R_cat = dict(zip(rc['产品分类'].astype(str), rc['R季节倍数'].astype(float)))
R_all = rc['R季节倍数'].astype(float).median()

def norm(c):
    c = str(c).strip()
    return c[:-1] if len(c) > 1 and c.endswith('色') else c

# 同品类在 JT_26 的均值基数（用于无销量款）
def cat_median_base(cat):
    sub = jt[jt['产品分类'] == cat].groupby('款式编码')['销售数量'].sum()
    return float(sub.median()) if len(sub) else 0.0
def cat_avg_price(cat):
    sub = jt[jt['产品分类'] == cat]
    s = sub['实发金额'].sum(); q = sub['销售数量'].sum()
    return (s/q) if q else 0.0
def cat_refund(cat):
    sub = jt[jt['产品分类'] == cat]
    s = sub['实发金额'].sum(); r = sub['实退金额'].sum()
    return (r/s) if s else 0.0

# 颜色拆分
def split_colors(code, user_colors, has_jt):
    sub = jt[jt['款式编码'] == code].copy()
    if '颜色规格' in sub.columns:
        sub['颜色'] = sub['颜色规格'].astype(str).str.split(';').str[0].str.strip()
    else:
        sub['颜色'] = sub['颜色'].astype(str).str.strip()
    g = sub.groupby('颜色')['销售数量'].sum()
    tot = g.sum()
    cs = {}
    if tot > 0:
        for col, q in g.items():
            cs[norm(col)] = q / tot
    present = {}; miss = []
    for uc in user_colors:
        nc = norm(uc)
        if nc in cs:
            present[uc] = cs[nc]
        else:
            miss.append(uc)
    psum = sum(present.values())
    flags = {}
    if miss:
        if psum > 0:
            floor = (psum / len(present)) * 0.5
            for uc in miss:
                present[uc] = floor; flags[uc] = '近期无销量-占比估算'
        else:
            floor = 1.0 / len(user_colors)
            for uc in miss:
                present[uc] = floor; flags[uc] = '无近15天销量-均分'
    s = sum(present.values())
    present = {k: v/s for k, v in present.items()}
    for uc in present:
        if uc not in flags:
            flags[uc] = 'JT近15天实际占比' if has_jt else '无近15天销量-均分'
    return present, flags

rows_skc = []
rows_style = []
missing_styles = []
diag_missing_colors = []
for code in codes:
    sub = jt[jt['款式编码'] == code]
    has_jt = len(sub) > 0
    if has_jt:
        cat = sub['产品分类'].iloc[0]
        base_q = sub['销售数量'].sum()
        base_amt = sub['实发金额'].sum()
        avg_price = base_amt / base_q if base_q else 0
        refund = (sub['实退金额'].sum() / sub['实发金额'].sum()) if sub['实发金额'].sum() else 0
        flag_base = 'JT近15天实际'
    else:
        # 推断品类：DD前缀→打底裤, KT前缀→裤套装
        cat = '打底裤' if code.startswith('XQ6DD') else ('裤套装' if code.startswith('XQ6KT') else '其它')
        base_q = cat_median_base(cat)
        avg_price = cat_avg_price(cat)
        refund = cat_refund(cat)
        flag_base = '无近15天销量-品类均值基数'
        missing_styles.append((code, cat, round(base_q,1)))
    R = R_cat.get(cat, R_all)
    est_q = base_q * R
    est_amt = est_q * avg_price
    net_q = est_q * (1 - refund)
    rows_style.append({
        '款式编码': code, '品类': cat, '近15天销量': round(base_q,1),
        'R倍数': round(R,3), '预估数量': round(est_q,1), '预估金额': round(est_amt),
        '退款率': round(refund,4), '净额(扣退款)': round(net_q,1),
        '基数来源': flag_base
    })
    shares, flags = split_colors(code, style_color[code], has_jt)
    for uc, sh in shares.items():
        rows_skc.append({
            '款式编码': code, '品类': cat, '颜色': uc,
            '颜色占比%': round(sh*100, 2), '预估数量': round(est_q*sh,1),
            '预估金额': round(est_amt*sh), '占比来源': flags[uc]
        })
    # 诊断缺色
    for uc, fl in flags.items():
        if fl != 'JT近15天实际占比':
            diag_missing_colors.append((code, uc, fl))

df_skc = pd.DataFrame(rows_skc)
df_style = pd.DataFrame(rows_style)

print('=== 诊断 ===')
print('款数', len(codes), 'SKC行数', len(df_skc))
print('无近15天销量的款(用品类均值基数):', missing_styles)
print('缺色SKC(非实际占比):', len(diag_missing_colors))
for x in diag_missing_colors: print('  ', x)
print()
print('=== 款式级预估 Top15 ===')
print(df_style.sort_values('预估数量', ascending=False).head(15).to_string(index=False))
print()
tot_q = df_style['预估数量'].sum(); tot_amt = df_style['预估金额'].sum()
tot_net = df_style['净额(扣退款)'].sum()
print(f'补充49款 合计: 数量 {tot_q:.0f}  金额 {tot_amt:.0f}  净额(扣退款) {tot_net:.0f}')
print(f'含3个无销量款(品类基数)的预估量: {df_style[df_style["基数来源"]!="JT近15天实际"]["预估数量"].sum():.0f}')

# 各类目R倍数 sheet 复制
rc_out = rc.copy()

# 退款率 sheet（当期，按款+按品类）
ref_style = df_style[['款式编码','品类','近15天销量','退款率','预估数量','净额(扣退款)']].copy()
ref_cat = df_style.groupby('品类').agg(退款率=('退款率','mean'), 预估数量=('预估数量','sum')).reset_index()
ref_cat['退款率'] = ref_cat['退款率'].round(4)

# 方法说明
notes = pd.DataFrame({
 '项目':[
   '预估方法','基数来源','R倍数口径','颜色拆分','缺色处理','退款率','净额','无销量款','3个无销量款明细','数据口径提醒'
 ],
 '说明':[
   'Method2 聚水潭同比：预估数量 = 26年近15天销量 × 同品类R_cat；R_cat=中位数(25年8.10-9.10销量÷25年同周期销量)',
   '46款取JT_26近15天实际销量；3款(XQ6DD508/DD509/KT552)近15天无销量，用同品类JT_26均值基数',
   '复用主表《各类目R倍数》，取同品类中位数；未匹配品类用全体中位数兜底',
   '按JT_26近15天各颜色实际销量占比拆分到SKC',
   '清单颜色在JT_26近15天无销量时，按同款已有颜色平均占比的50%估算再整体归一，标注"近期无销量-占比估算"；款无销量则均分标注"无近15天销量-均分"',
   '当期实退金额÷实发金额（JT_26实际）；缺销量款用同品类退款率',
   '净额 = 预估数量 ×(1-退款率)，为扣退款后实际可落袋量',
   'XQ6DD508/DD509→打底裤；XQ6KT552→裤套装（按同前缀兄弟款品类推断）',
   'DD508基数=打底裤品类均值, DD509同, KT552基数=裤套装品类均值',
   '3款无销量基数偏假设性，建议结合上新节奏人工复核；其余46款近15天基数薄，R放大后误差会被放大'
 ]
})

with pd.ExcelWriter(OUT, engine='openpyxl') as xw:
    df_skc.to_excel(xw, sheet_name='SKC级预估', index=False)
    df_style.to_excel(xw, sheet_name='款式级预估', index=False)
    rc_out.to_excel(xw, sheet_name='各类目R倍数', index=False)
    ref_style.to_excel(xw, sheet_name='退款率(当期)', index=False)
    ref_cat.to_excel(xw, sheet_name='退款率(品类)', index=False)
    notes.to_excel(xw, sheet_name='方法说明', index=False)
print('\n已保存:', OUT)

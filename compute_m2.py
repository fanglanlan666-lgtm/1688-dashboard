import pandas as pd, re, numpy as np, json

skc_text = ("XQ6CS427 粉紫 XQ6CS427 白色 XQ6DD507 深灰 XQ6DD507 黑色 XQ6DD507 藏青 "
"XQ6DD507 浅灰 XQ6KT551 粉色 XQ6KT551 杏色 XQ6KT553 粉色 XQ6KT553 花灰 "
"XQ6KT554 粉色 XQ6KT554 酒红 XQ6KT554 藏青色 XQ6MY441 花灰色 XQ6MY441 咖色 "
"XQ6MY441 黑色 XQ6MY441 藏青色 XQ6MY441 藏青 XQ6MY441 花灰 XQ6NZ533 蓝色 "
"XQ6QK510 浅灰 XQ6QK510 深紫 XQ6QK510 深灰 XQ6SK527 酒红色 XQ6SK527 藏青 "
"XQ6TX405 咖色 XQ6TX405 粉色 XQ6TX405 白色 XQ6TX405 红色 XQ6TX406 奶黄 "
"XQ6TX406 灰紫 XQ6TX406 浅粉 XQ6TX406 杏色 XQ6TX407 黄色 XQ6TX407 米色 "
"XQ6TX410 粉色 XQ6TX410 藏青 XQ6TX410 白色 XQ6TX414 藏青 XQ6TX414 杏色 "
"XQ6TX414 粉色 XQ6TX414 紫红 XQ6TX570 花灰 XQ6TX570 藏青 XQ6WT483 橘色 "
"XQ6WT483 浅紫 XQ6WT483 黄色 XQ6WT483 黑色 XQ6WT485 黄色 XQ6WT485 玫红 "
"XQ6WT485 藏青 XQ6WT487 黄色 XQ6WT487 蓝色 XQ6WT487 玫红 XQ6WT488 大红 "
"XQ6WT488 黄色 XQ6WY433 玫红 XQ6WY433 大红 XQ6WY433 深咖 XQ6WY433 紫色 "
"XQ6WY433 粉色 XQ6WY436 杏色 XQ6WY436 深灰 XQ6WY436 紫色 XQ6WY436 粉色")
pairs = re.findall(r'(XQ6\w+)\s+([^\s]+)', skc_text)
style_color = {}
for code, color in pairs:
    style_color.setdefault(code, []).append(color)
codes = list(style_color.keys())

def load(f):
    d = pd.read_excel(f)
    d['款式编码'] = d['款式编码'].astype(str).str.strip()
    d = d[~d['款式编码'].str.contains('#|总|计', na=False)]
    d['颜色规格'] = d['颜色规格'].astype(str).str.strip()
    d['颜色'] = d['颜色规格'].str.split(';').str[0].str.strip()
    d['销售数量'] = pd.to_numeric(d['销售数量'], errors='coerce')
    d['销售金额'] = pd.to_numeric(d['销售金额'], errors='coerce')
    return d

jt26 = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155006_183907082_1.xlsx")
jt25c = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155110_183907502_1.xlsx")
jt25l = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155151_183907820_1.xlsx")

# 颜色归一化：用户色 -> JT色（处理 藏青色->藏青, 酒红色->酒红）
def norm_color(c):
    return {'藏青色':'藏青','酒红色':'酒红'}.get(c, c)

# 25年可比款季节倍数 R = S25late / S25c（同品类中位数）
def agg_by_style(df):
    g = df.groupby('款式编码').agg(销量=('销售数量','sum'), 分类=('产品分类','first')).reset_index()
    return g
a25c = agg_by_style(jt25c); a25l = agg_by_style(jt25l)
m25 = a25c.merge(a25l, on='款式编码', how='inner', suffixes=('_c','_l'))
m25 = m25[m25['销量_c']>0]
m25['R'] = m25['销量_l'] / m25['销量_c']
m25 = m25.rename(columns={'分类_c':'分类'})
print("DEBUG m25 cols:", m25.columns.tolist())
# 按分类中位数
R_cat = m25.groupby('分类')['R'].median()
R_all = m25['R'].median()
print("25年可比款(两文件共有)数:", len(m25))
print("整体季节倍数中位数 R_all =", round(R_all,3))
print("\n各类目季节倍数中位数 R_cat:")
for cat, r in R_cat.items():
    print(f"  {cat}: R={r:.3f} (样本{np.sum(m25['分类']==cat)})")

# 26近15天
a26 = agg_by_style(jt26)
a26 = a26.set_index('款式编码')

# 逐款预估
print("\n=== 21款 Method2 预估 ===")
rows=[]
for c in codes:
    s26 = a26.loc[c,'销量'] if c in a26.index else 0
    cat = a26.loc[c,'分类'] if c in a26.index else '未知'
    R = R_cat.get(cat, R_all)
    est = s26 * R
    up = jt26[jt26['款式编码']==c]
    q=up['销售数量'].sum(); am=up['销售金额'].sum()
    unit = am/q if q>0 else 0
    rows.append((c, cat, s26, round(R,3), round(est,1), round(est*unit,1)))
df = pd.DataFrame(rows, columns=['款式编码','产品分类','S26近15天','R倍数','预估数量','预估金额'])
print(df.to_string(index=False))
print("\n预估总量:", round(df['预估数量'].sum()), "件 /", round(df['预估金额'].sum()), "元")

# 保存中间结果供后续生成
df.to_json(r"C:\Users\Administrator\WorkBuddy\1688业务\m2_style.json", orient='records', force_ascii=False)
R_cat.to_json(r"C:\Users\Administrator\WorkBuddy\1688业务\R_cat.json", force_ascii=False)
print("\nR_all=", round(R_all,3))

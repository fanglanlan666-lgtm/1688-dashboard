import pandas as pd, re
pd.set_option('display.max_rows', 200)

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
    d['销售数量'] = pd.to_numeric(d['销售数量'], errors='coerce')
    d['销售金额'] = pd.to_numeric(d['销售金额'], errors='coerce')
    return d

jt26 = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155006_183907082_1.xlsx")
jt25c = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155110_183907502_1.xlsx")
jt25l = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155151_183907820_1.xlsx")

c25c = set(jt25c['款式编码']); c25l = set(jt25l['款式编码'])
print("21款 vs JT_25同周期 重叠:", [c for c in codes if c in c25c])
print("21款 vs JT_25年late 重叠:", [c for c in codes if c in c25l])

# JT_26 实际颜色命名 for 21 styles
print("\n=== JT_26 各款实际颜色规格 ===")
for c in codes:
    sub = jt26[jt26['款式编码'] == c]
    cols = sorted(set(sub['颜色规格']))
    print(f"{c}: {cols}")
    # 单价
    q = sub['销售数量'].sum(); a = sub['销售金额'].sum()
    print(f"   销量={q:.0f} 金额={a:.0f} 单价={a/q if q else 0:.2f}")

import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)

# ---- sycm content ----
sycm = pd.read_excel(r"D:\Downloads\sycm (8).xlsx")
print("=== sycm 前3行原始值（定位指标列）===")
for r in range(3):
    print(f"--- row {r} ---")
    for i, c in enumerate(sycm.columns):
        v = sycm.iloc[r, i]
        s = str(v)
        print(f"  col[{i}] {c!r}: {s[:50]}")

# ---- JT checks ----
def load(f):
    d = pd.read_excel(f)
    d['款式编码'] = d['款式编码'].astype(str).str.strip()
    d['颜色规格'] = d['颜色规格'].astype(str).str.strip()
    d['销售数量'] = pd.to_numeric(d['销售数量'], errors='coerce')
    return d

jt26 = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155006_183907082_1.xlsx")
jt25c = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155110_183907502_1.xlsx")
jt25l = load(r"C:\360极速浏览器下载\销售主题分析_商品_20260810155151_183907820_1.xlsx")

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
import re
pairs = re.findall(r'(XQ6\w+)\s+([^\s]+)', skc_text)
style_color = {}
for code, color in pairs:
    style_color.setdefault(code, []).append(color)
codes = list(style_color.keys())
print(f"\n=== SKC清单: {len(codes)}款, {len(pairs)}个SKC ===")

c26 = set(jt26['款式编码']); c25c = set(jt25c['款式编码']); c25l = set(jt25l['款式编码'])
print(f"JT_26近15天 款式数={len(c26)}; JT_25同周期={len(c25c)}; JT_25年8.10-9.10={len(c25l)}")
print(f"26 vs 25同周期 重叠={len(c26 & c25c)}; 26 vs 25late 重叠={len(c26 & c25l)}; 25c vs 25l 重叠={len(c25c & c25l)}")

cov = [c for c in codes if c in c26]
print(f"\nSKC清单款在JT_26近15天覆盖: {len(cov)}/{len(codes)} 款")
print("未覆盖款:", [c for c in codes if c not in c26])
miss_color = []
for c in cov:
    sub = jt26[jt26['款式编码'] == c]
    cols = set(sub['颜色规格'])
    for col in style_color[c]:
        if col not in cols:
            miss_color.append((c, col))
print("颜色缺失总数:", len(miss_color))
print("颜色缺失样例:", miss_color[:40])

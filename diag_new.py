import pandas as pd, numpy as np

NB = r"C:\360极速浏览器下载\销售主题分析_款_20260731100225_181285979_1.xlsx"
ND = r"C:\360极速浏览器下载\销售主题分析_商品_20260731100238_181286089_1.xlsx"
A  = r"C:\360极速浏览器下载\25.7.30-25.8.15.xlsx"
C  = r"C:\360极速浏览器下载\销售主题分析_款_20260731091733_181260081_1.xlsx"

def load(f, col):
    d = pd.read_excel(f); d['code'] = d[col].astype(str).str.strip()
    d = d[~d['code'].str.contains('#|总|计', na=False)]
    for c in ['销售数量','销售金额']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    return d

Bn = load(NB,'款式编码/商品编码')
Dn = load(ND,'款式编码')
An = load(A,'款式编码/商品编码')
Cn = load(C,'款式编码/商品编码')

print("=== 新款式表 NB 列 ===", list(Bn.columns))
print("NB shape:", Bn.shape, " 销量合计:", round(Bn['销售数量'].sum()))
print("NB 虚拟分类分布:")
print(Bn['虚拟分类'].value_counts(dropna=False).head(25).to_string())
print()
print("=== 新商品表 ND 列(前15) ===", list(Dn.columns)[:15], "...")
print("ND shape:", Dn.shape, " 销量合计:", round(Dn['销售数量'].sum()))
if '虚拟分类' in Dn.columns:
    print("ND 虚拟分类分布:")
    print(Dn['虚拟分类'].value_counts(dropna=False).head(15).to_string())

# 清单
list_codes = sorted(set("""XQ6CS426 XQ6CS427 XQ6CS429 XQ6DD507 XQ6DQ501 XQ6DQ503 XQ6KT551 XQ6KT553 XQ6LY542 XQ6MJ463 XQ6MJ466 XQ6MY441 XQ6NZ533 XQ6NZ537 XQ6NZ538 XQ6QK510 XQ6QK563 XQ6SK522 XQ6SK523 XQ6SK526 XQ6SK527 XQ6TX402 XQ6TX405 XQ6TX406 XQ6TX407 XQ6TX409 XQ6TX414 XQ6TX416 XQ6TX422 XQ6TX430 XQ6TX570 XQ6WT473 XQ6WT476 XQ6WT485 XQ6WT487 XQ6WT488 XQ6WY433 XQ6WY436 XQ6WY439 XQ6ZK511 XQ6ZK516 XQ6ZK520""".split()))

# 清单款式×颜色
raw = """XQ6QK510	浅灰
XQ6ZK520	黑色
XQ6QK510	深紫
XQ6QK510	深灰
XQ6ZK520	粉色
XQ6CS427	粉紫
XQ6ZK516	深灰
XQ6ZK516	浅粉
XQ6ZK516	紫红
XQ6DQ503	藏青
XQ6ZK516	花灰
XQ6CS427	白色
XQ6DQ503	咖色
XQ6DD507	深灰
XQ6DD507	黑色
XQ6DD507	藏青
XQ6MJ463	粉色
XQ6MJ463	玫紫
XQ6MJ463	黄绿
XQ6DD507	浅灰
XQ6TX422	浅卡其
XQ6TX422	杏色
XQ6NZ533	蓝色
XQ6TX422	粉色
XQ6SK526	深灰
XQ6TX405	咖色
XQ6TX405	粉色
XQ6KT551	粉色
XQ6WT487	黄色
XQ6WT487	蓝色
XQ6WT487	玫红
XQ6TX405	白色
XQ6QK563	粉色
XQ6KT551	杏色
XQ6QK563	黑白
XQ6SK526	赤红
XQ6TX405	红色
XQ6WT473	花灰
XQ6TX407	黄色
XQ6TX402	米色
XQ6WT488	大红
XQ6WY439	米色
XQ6TX402	黄色
XQ6WT488	黄色
XQ6TX407	米色
XQ6ZK520	深灰
XQ6WY439	粉色
XQ6TX402	紫色
XQ6TX402	嫩绿
XQ6ZK511	藏青
XQ6ZK511	咖色
XQ6ZK511	深灰
XQ6WY436	杏色
XQ6WY436	深灰
XQ6WY436	紫色
XQ6WY436	粉色
XQ6WY433	玫红
XQ6WY433	大红
XQ6WY433	深咖
XQ6WY433	紫色
XQ6WY433	粉色
XQ6WT485	黄色
XQ6WT485	玫红
XQ6WT485	藏青
XQ6WT476	紫色
XQ6WT476	藏青色
XQ6TX570	花灰
XQ6TX570	藏青
XQ6TX430	深灰
XQ6TX430	米色
XQ6TX430	粉色
XQ6TX416	白色
XQ6TX414	藏青
XQ6TX414	杏色
XQ6TX414	粉色
XQ6TX409	黄色
XQ6TX409	蓝色
XQ6TX406	奶黄
XQ6TX406	灰紫
XQ6TX406	浅粉
XQ6TX406	杏色
XQ6SK527	酒红色
XQ6SK527	藏青
XQ6SK523	绿色
XQ6SK523	粉色
XQ6SK523	紫色
XQ6SK522	粉色
XQ6SK522	酒红色
XQ6SK522	杏色
XQ6NZ538	深蓝
XQ6NZ538	蓝色
XQ6NZ537	蓝色
XQ6NZ537	藏青
XQ6MY441	花灰色
XQ6MY441	咖色
XQ6MY441	黑色
XQ6MY441	藏青色
XQ6MY441	藏青
XQ6MY441	花灰
XQ6MJ466	黑色
XQ6LY542	咖色
XQ6LY542	粉色
XQ6LY542	杏色
XQ6KT553	粉色
XQ6KT553	花灰
XQ6DQ501	紫色
XQ6DQ501	杏色
XQ6DQ501	浅蓝
XQ6DQ501	粉色
XQ6CS429	绿色
XQ6CS429	粉色
XQ6CS429	黄色
XQ6CS426	嫩绿
XQ6CS426	米色"""
pairs = [tuple(l.split('\t')) for l in raw.strip().splitlines()]
dfp = pd.DataFrame(pairs, columns=['款式编码','颜色'])

def q(df, code):
    return pd.to_numeric(df[df['code']==code]['销售数量'], errors='coerce').sum()

print("\n=== 清单款 在新旧文件的销量对比 ===")
print(f"{'款式':12s} {'B新(26e)':>9s} {'A(25late)':>10s} {'C(25e)':>9s}")
totB=totA=totC=0
for s in list_codes:
    b=q(Bn,s); a=q(An,s); c=q(Cn,s)
    totB+=b; totA+=a; totC+=c
    print(f"{s:12s} {b:9.0f} {a:10.0f} {c:9.0f}")
print(f"{'合计':12s} {totB:9.0f} {totA:10.0f} {totC:9.0f}")
print(f"\n在B新(26early)有销量: {(np.array([q(Bn,s) for s in list_codes])>0).sum()}/{len(list_codes)}")
print(f"在A(25late)有销量:   {(np.array([q(An,s) for s in list_codes])>0).sum()}/{len(list_codes)}")
print(f"在C(25early)有销量:   {(np.array([q(Cn,s) for s in list_codes])>0).sum()}/{len(list_codes)}")

# D新 颜色覆盖
Dsub = Dn.assign(color=Dn['颜色规格'].astype(str).str.split(';').str[0].str.strip())
print("\n=== 新商品表 ND 颜色覆盖 ===")
print("清单款在ND有颜色明细:", Dn['code'].isin(list_codes).sum(), "款")
hit = sum(1 for _,r in dfp.iterrows() if len(Dsub[(Dsub['code']==r['款式编码'])&(Dsub['color']==r['颜色'])])>0)
print(f"清单SKC在ND精确匹配(款式+颜色): {hit}/{len(dfp)}")
PY
import pandas as pd, numpy as np, re

# ---- 用户提供的款式×颜色清单 ----
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

pairs = []
for line in raw.strip().splitlines():
    code, color = line.split('\t')
    pairs.append((code.strip(), color.strip()))
df_pairs = pd.DataFrame(pairs, columns=['款式编码','颜色'])
styles = sorted(df_pairs['款式编码'].unique())
print("清单 SKC 条目数:", len(df_pairs), " 去重款式数:", len(styles))

# ---- 加载四文件 ----
PATH = {
 "A": r"C:\360极速浏览器下载\25.7.30-25.8.15.xlsx",
 "B": r"C:\360极速浏览器下载\销售主题分析_款_20260731091709_181259840_1.xlsx",
 "C": r"C:\360极速浏览器下载\销售主题分析_款_20260731091733_181260081_1.xlsx",
 "D": r"C:\360极速浏览器下载\销售主题分析_商品_20260731092116_181262652_1.xlsx",
}
def load(f, col):
    d = pd.read_excel(f); d['code'] = d[col].astype(str).str.strip()
    d = d[~d['code'].str.contains('#|总|计', na=False)]
    for c in ['销售数量','销售金额']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    return d
A = load(PATH['A'],'款式编码/商品编码'); B = load(PATH['B'],'款式编码/商品编码')
C = load(PATH['C'],'款式编码/商品编码'); D = load(PATH['D'],'款式编码')

def qty(df, code, col='销售数量'):
    sub = df[df['code']==code]
    return pd.to_numeric(sub[col], errors='coerce').sum()

# 覆盖诊断
inB = [s for s in styles if qty(B,s)>0]
inA = [s for s in styles if qty(A,s)>0]
inC = [s for s in styles if qty(C,s)>0]
print(f"\n款式覆盖: 在B(26early)={len(inB)}/{len(styles)}  在A(25late)={len(inA)}  在C(25early)={len(inC)}")
both_BC = [s for s in styles if qty(B,s)>0 and qty(C,s)>0]
both_AB = [s for s in styles if qty(A,s)>0 and qty(B,s)>0]
print(f"同时有B&C(可做同比分子)={len(both_BC)}  同时有A&B={len(both_AB)}")

# 每个款式在B/C/A的实际销量
print("\n款式   B(26early)  C(25early)  A(25late)  虚拟分类")
for s in styles:
    b=qty(B,s); c=qty(C,s); a=qty(A,s)
    vc = B[B['code']==s]['虚拟分类']
    vc = vc.dropna().astype(str).iloc[0] if len(vc.dropna()) else (C[C['code']==s]['虚拟分类'].dropna().astype(str).iloc[0] if len(C[C['code']==s]['虚拟分类'].dropna()) else '-')
    print(f"  {s}  B={b:6.0f}  C={c:6.0f}  A={a:6.0f}  {vc}")

# D颜色覆盖：清单款式在D中有颜色明细吗
Dstyle = set(D['code'])
print("\n清单款式在D(商品表)中有颜色明细:", len(set(styles)&Dstyle), "/", len(styles))
# 对清单中每个颜色，看D是否有该款式该颜色
Dsub = D.assign(color=D['颜色规格'].astype(str).str.split(';').str[0].str.strip())
hit=0
for _,r in df_pairs.iterrows():
    m = Dsub[(Dsub['code']==r['款式编码']) & (Dsub['color']==r['颜色'])]
    if len(m): hit+=1
print("清单SKC在D中能精确匹配(款式+颜色):", hit, "/", len(df_pairs))
PY
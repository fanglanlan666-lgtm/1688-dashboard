import pandas as pd, sys, re
sys.stdout.reconfigure(encoding='utf-8')

# ---- sycm ----
s = pd.read_excel('D:/Downloads/sycm (8).xlsx', header=None)
sycm = []
for i in range(1, len(s)):
    r = s.iloc[i]
    link = str(r[0]); m = re.search(r'/offer/(\d+)', link)
    offer = m.group(1) if m else ''
    title = str(r[2])
    if '童贝' not in title and '1688' not in title:
        continue
    def num(x):
        try: return float(str(x).replace(',', '').replace('%', ''))
        except: return 0
    sycm.append({'offer': offer, 'title': title,
                 '访客': int(num(r[3])), '支付转化率': num(r[7]), '加购率': num(r[8])})
print('sycm 有效行:', len(sycm))

# ---- 21 XQ6 ----
jt = pd.read_excel('C:/360极速浏览器下载/销售主题分析_商品_20260810155006_183907082_1.xlsx')
jt['款式编码'] = jt['款式编码'].astype(str).str.strip()
st = pd.read_excel('26年8.10-9.10_XQ6新款_SKC预估.xlsx', sheet_name='款式级预估', header=2).dropna(subset=['款式编码'])
codes = st['款式编码'].astype(str).str.strip().tolist()
name = jt[jt['款式编码'].isin(codes)].groupby('款式编码')['商品简称'].first().to_dict()

# ---- 品类判定（修正顺序：套装优先，牛仔裤需精确） ----
def cat_xq6(n):
    if '衬衫' in n: return '衬衫'
    if '裤套装' in n or '套装' in n: return '裤套装'
    if '卫衣' in n: return '卫衣'
    if '牛仔裤' in n: return '牛仔裤'
    if '休闲裤' in n or '格子' in n: return '休闲裤'
    if '背心' in n or '针织' in n: return '背心针织衫'
    if 'T恤' in n: return 'T恤'
    if '打底裤' in n: return '打底裤'
    if '外套' in n: return '外套'
    return '其他'

def cat_sycm(t):
    if '衬衫' in t: return '衬衫'
    if '裤套装' in t or '两件套' in t or '套装' in t: return '裤套装'
    if '卫衣' in t or '绒衫' in t: return '卫衣'
    if '牛仔裤' in t: return '牛仔裤'
    if '休闲裤' in t or '格' in t: return '休闲裤'
    if '马甲' in t or '背心' in t or '针织' in t or '毛衣' in t: return '背心针织衫'
    if 'T恤' in t or '上衣' in t: return 'T恤'
    if '打底裤' in t or '鲨鱼' in t or '踩脚' in t: return '打底裤'
    if '外套' in t or '冲锋衣' in t or '棒球服' in t or '夹克' in t or '棉服' in t or '大衣' in t: return '外套'
    return '其他'

FEAT = ['条纹','连帽','插肩','撞色','假两件','格子','净色','纯色','圆领','图案','花边','翻领','立领','拉链','拼接','纱摆','印花','卫衣裤','打底裤套装','马甲','背心','针织','毛衣','冲锋衣','棒球服','斑点狗','小象','大象','小狗','长袖','套头','绒衫','休闲裤','荷叶边']
def feats(t):
    return set(f for f in FEAT if f in t)

def score(n, t):
    c1, c2 = cat_xq6(n), cat_sycm(t)
    base = 5 if c1 == c2 else -20
    return base + len(feats(n) & feats(t))

# ---- 贪心分配：高分优先，同款不重复占用 ----
# 每个 XQ6 的候选池（同品类），按 score 排序
cands = {}
for c in codes:
    n = name[c]
    pool = [i for i, r in enumerate(sycm) if cat_sycm(r['title']) == cat_xq6(n)] or list(range(len(sycm)))
    cands[c] = sorted(pool, key=lambda i: score(n, sycm[i]['title']), reverse=True)

# 按各 XQ6 与其最优候选的差距排序，贪心认领
order = sorted(codes, key=lambda c: score(name[c], sycm[cands[c][0]]['title']) if cands[c] else -999, reverse=True)
used = set()
assign = {}
for c in order:
    for i in cands[c]:
        if i not in used:
            used.add(i); assign[c] = i; break
    else:
        assign[c] = None

# ---- 输出 ----
rows_out = []
for c in codes:
    i = assign[c]
    if i is None:
        rows_out.append({'款号': c, '商品简称': name[c], '品类': cat_xq6(name[c]),
                         '候选sycm标题': '（未匹配，请手填）', 'offer': '', '访客': '', '支付转化率': '', '加购率': '', '确认': ''})
        continue
    r = sycm[i]
    rows_out.append({'款号': c, '商品简称': name[c], '品类': cat_xq6(name[c]),
                     '候选sycm标题': r['title'], 'offer': r['offer'], '访客': int(r['访客']),
                     '支付转化率': round(r['支付转化率']/100, 4), '加购率': round(r['加购率']/100, 4), '确认': ''})

df_out = pd.DataFrame(rows_out, columns=['款号','商品简称','品类','候选sycm标题','offer','访客','支付转化率','加购率','确认'])
df_out.to_excel('Method1_映射候选.xlsx', index=False)
print('已生成 Method1_映射候选.xlsx ，覆盖', sum(1 for x in rows_out if x['offer']), '/', len(codes))
print('\n=== 最终候选映射 ===')
for x in rows_out:
    print(f"{x['款号']} [{x['品类']}] {x['商品简称'][:10]} → {x['候选sycm标题'][:30]} (访客{x['访客']}, 转化{x['支付转化率']}, 加购{x['加购率']})")

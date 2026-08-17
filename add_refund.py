import pandas as pd, sys
from openpyxl import Workbook
from openpyxl.styles import Font
sys.stdout.reconfigure(encoding='utf-8')

BOOK = '26年8.10-9.10_XQ6新款_SKC预估.xlsx'
JT = 'C:/360极速浏览器下载/销售主题分析_商品_20260810155006_183907082_1.xlsx'

st = pd.read_excel(BOOK, sheet_name='款式级预估', header=2)
codes = st['款式编码'].astype(str).str.strip().tolist()

df = pd.read_excel(JT)
df['款式编码'] = df['款式编码'].astype(str).str.strip()
sub = df[df['款式编码'].isin(codes)]

g = sub.groupby('款式编码').agg(
    实发金额=('实发金额', 'sum'), 实退金额=('实退金额', 'sum'),
    实发数量=('实发数量', 'sum'), 实退数量=('实退数量', 'sum')).reset_index()
g['退款率_金额'] = (g['实退金额'] / g['实发金额']).round(4)
g['退款率_件数'] = (g['实退数量'] / g['实发数量']).round(4)

# 品类小计
cat = sub.groupby('产品分类').agg(
    实发金额=('实发金额', 'sum'), 实退金额=('实退金额', 'sum'),
    实发数量=('实发数量', 'sum'), 实退数量=('实退数量', 'sum')).reset_index()
cat['退款率_金额'] = (cat['实退金额'] / cat['实发金额']).round(4)
cat['退款率_件数'] = (cat['实退数量'] / cat['实发数量']).round(4)

# 整体
tr = g['实退金额'].sum(); ts = g['实发金额'].sum()
trn = g['实退数量'].sum(); tsn = g['实发数量'].sum()
overall = {'款式编码': '▶ 整体', '实发金额': round(ts), '实退金额': round(tr),
           '实发数量': round(tsn), '实退数量': round(trn),
           '退款率_金额': round(tr / ts, 4), '退款率_件数': round(trn / tsn, 4)}

# ---- 写入新 workbook ----
OUT = '退款率_XQ6当期.xlsx'
wb = Workbook()
ws = wb.active
ws.title = '退款率(当期)'

def put(r, c, v, bold=False, pct=False):
    cell = ws.cell(row=r, column=c, value=v)
    if bold:
        cell.font = Font(bold=True)
    if pct and isinstance(v, (int, float)):
        cell.number_format = '0.00%'
    return cell

r = 1
put(r, 1, '26年秋款 XQ6 · 当期(26近15天实际) 退款率 = 实退金额 / 实发金额', bold=True)
r += 1
hdr = ['款式编码', '实发金额', '实退金额', '实发数量', '实退数量', '退款率(金额)', '退款率(件数)']
for c, h in enumerate(hdr, 1):
    put(r, c, h, bold=True)
r += 1
for _, row in g.iterrows():
    put(r, 1, row['款式编码'])
    put(r, 2, round(row['实发金额'], 2))
    put(r, 3, round(row['实退金额'], 2))
    put(r, 4, int(row['实发数量']))
    put(r, 5, int(row['实退数量']))
    put(r, 6, row['退款率_金额'], pct=True)
    put(r, 7, row['退款率_件数'], pct=True)
    r += 1
# 整体
put(r, 1, overall['款式编码'], bold=True)
put(r, 2, overall['实发金额'], bold=True)
put(r, 3, overall['实退金额'], bold=True)
put(r, 4, overall['实发数量'], bold=True)
put(r, 5, overall['实退数量'], bold=True)
put(r, 6, overall['退款率_金额'], bold=True, pct=True)
put(r, 7, overall['退款率_件数'], bold=True, pct=True)
r += 2
put(r, 1, '按品类小计', bold=True); r += 1
for c, h in enumerate(['产品分类', '实发金额', '实退金额', '实发数量', '实退数量', '退款率(金额)', '退款率(件数)'], 1):
    put(r, c, h, bold=True)
r += 1
for _, row in cat.iterrows():
    put(r, 1, row['产品分类'])
    put(r, 2, round(row['实发金额'], 2))
    put(r, 3, round(row['实退金额'], 2))
    put(r, 4, int(row['实发数量']))
    put(r, 5, int(row['实退数量']))
    put(r, 6, row['退款率_金额'], pct=True)
    put(r, 7, row['退款率_件数'], pct=True)
    r += 1
r += 1
put(r, 1, '说明：近15天新款退款尚未完全回流，标0%款式多为刚上新、退款未产生；整体10.84%为当期实际值。', bold=False)

# 列宽
widths = [12, 12, 12, 11, 11, 14, 14]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[chr(64 + i)].width = w

wb.save(OUT)
print('已写入 退款率(当期) sheet')
print('整体退款率(金额) %.2f%%  退款率(件数) %.2f%%' % (overall['退款率_金额']*100, overall['退款率_件数']*100))
print('gross 预估数量 1463 → 扣退款净额 ≈', round(1463*(1-overall['退款率_件数'])))

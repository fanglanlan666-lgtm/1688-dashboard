import json, re, glob, os

# 1) sycm links
import pandas as pd
sycm = pd.read_excel(r"D:\Downloads\sycm (8).xlsx")
sycm_links = sycm.iloc[:, 0].astype(str).str.strip().tolist()
sycm_offers = []
for l in sycm_links:
    m = re.search(r'/offer/(\d+)', l)
    sycm_offers.append(m.group(1) if m else l)

# 2) feishu mapping
pairs = []
for f in ["feishu_rec.json"] + sorted(glob.glob(r"C:\Users\Administrator\WorkBuddy\1688业务\pg_*.json")):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    data = d.get('data', {})
    rows = data.get('data', []) if isinstance(data, dict) else []
    for r in rows:
        if isinstance(r, list) and len(r) >= 2:
            link, kh = r[0], r[1]
            if not link or not kh:
                continue
            m = re.search(r'/offer/(\d+)', str(link))
            offer = m.group(1) if m else str(link)
            pairs.append((offer, str(kh).strip()))
print("飞书映射总条数:", len(pairs))
# dict offer->款号 (last wins)
omap = {}
for offer, kh in pairs:
    omap.setdefault(offer, kh)
print("唯一offer数:", len(omap))

# 3) match sycm
matched = 0
unmatched = []
sycm_to_kh = {}
for offer in sycm_offers:
    if offer in omap:
        matched += 1
        sycm_to_kh[offer] = omap[offer]
    else:
        unmatched.append(offer)
print(f"\nsycm链接数={len(sycm_offers)} 匹配到款号={matched} 未匹配={len(unmatched)}")
print("未匹配样例(offer):", unmatched[:15])
# show matched kh distribution
from collections import Counter
khc = Counter(sycm_to_kh.values())
print("\n匹配到的款号(去重)数:", len(khc))
print("样例款号:", list(khc)[:20])
# 本次SKC清单21款覆盖
skc_text = ("XQ6CS427 XQ6DD507 XQ6KT551 XQ6KT553 XQ6KT554 XQ6MY441 XQ6NZ533 "
"XQ6QK510 XQ6SK527 XQ6TX405 XQ6TX406 XQ6TX407 XQ6TX410 XQ6TX414 XQ6TX570 "
"XQ6WT483 XQ6WT485 XQ6WT487 XQ6WT488 XQ6WY433 XQ6WY436")
skc_codes = set(re.findall(r'(XQ6\w+)', skc_text))
matched_kh_set = set(sycm_to_kh.values())
print("\nSKC清单21款在sycm匹配到的:", sorted(skc_codes & matched_kh_set))
print("SKC清单21款未在sycm匹配到的:", sorted(skc_codes - matched_kh_set))

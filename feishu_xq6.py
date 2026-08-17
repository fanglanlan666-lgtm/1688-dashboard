import json, sys, subprocess, time, os
sys.stdout.reconfigure(encoding='utf-8')

CLI = "C:/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/node_modules/@larksuite/cli"
NODE = "C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe"
BASE = "HLOQbPqJJa4N60sVeL7cFcShnGd"
TBL = "tblxLgoFJWWfHozn"
OUT = "C:/Users/Administrator/WorkBuddy/1688业务"

fl = json.load(open(f"{OUT}/fl_xq6.json", encoding='utf-8'))
id2name = {x['id']: x['name'] for x in fl['data']['hint']['fields']['fields']}

def run(args):
    for attempt in range(6):
        try:
            p = subprocess.run([NODE, "scripts/run.js", "base"] + args,
                               cwd=CLI, capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                return json.loads(p.stdout)
            print("  retry rc", p.returncode, p.stderr[:120])
        except Exception as e:
            print("  retry err", str(e)[:120])
        time.sleep(3)
    raise RuntimeError("lark-cli failed")

# page 0 already saved
all_rows = []
page = 0
offset = 0
has_more = True
while has_more and page < 40:
    if page == 0:
        d = json.load(open(f"{OUT}/pg_xq6_0.json", encoding='utf-8'))
    else:
        d = run(["+record-list", "--base-token", BASE, "--table-id", TBL,
                 "--limit", "200", "--offset", str(offset), "--format", "json", "--as", "user"])
    data = d['data']
    fids = data['field_id_list']
    recs = data['data']
    for r in recs:
        all_rows.append({id2name.get(fids[i], fids[i]): r[i] for i in range(min(len(fids), len(r)))})
    has_more = data.get('has_more', False)
    offset += len(recs)
    page += 1
    if page % 5 == 0:
        print("page", page, "累计", len(all_rows), "has_more", has_more)

print("TOTAL records:", len(all_rows))
kds = [r.get('款号') for r in all_rows if r.get('款号')]
print("distinct 款号:", len(set(kds)))
dates = set(str(r.get('日期'))[:10] for r in all_rows if r.get('日期'))
print("distinct 日期:", sorted(dates)[:10], "...共", len(dates))
xq6 = [r for r in all_rows if isinstance(r.get('款号'), str) and r['款号'].startswith('XQ6')]
print("XQ6 records:", len(xq6))
print("XQ6 distinct 款号:", sorted(set(r['款号'] for r in xq6)))
json.dump(all_rows, open(f"{OUT}/xq6_all.json", "w", encoding='utf-8'), ensure_ascii=False)
print("saved xq6_all.json")

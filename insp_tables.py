import os, json, subprocess, time
LARK_BIN = r"C:/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/node_modules/@larksuite/cli/bin/lark-cli.exe"
BASE = "HLOQbPqJJa4N60sVeL7cFcShnGd"

def run(args, retries=6):
    last=None
    for i in range(retries):
        try:
            p=subprocess.run([LARK_BIN]+args, capture_output=True, text=True, timeout=180)
            if p.returncode!=0:
                err=(p.stderr or p.stdout).strip()
                if any(k in err for k in ("Permission denied","Resource temporarily unavailable","拒绝访问")):
                    last=err; time.sleep(3); continue
                raise RuntimeError("lark fail: "+err[:300])
            return p.stdout
        except (subprocess.SubprocessError, OSError) as e:
            last=str(e)
            if i<retries-1: time.sleep(3); continue
            raise
    raise RuntimeError("retry fail: "+str(last)[:200])

def inspect(tid, label):
    print("\n===== %s (%s) =====" % (label, tid))
    out=run(["base","+record-list","--base-token",BASE,"--table-id",tid,"--limit","3","--format","json","--as","user"])
    obj=json.loads(out); d=obj["data"]
    names=d.get("fields") or d.get("field_id_list")
    data=d.get("data") or []
    print("fields(%d):" % len(names), names)
    for i,vals in enumerate(data[:2]):
        print("-- row",i,"--")
        rec={names[j]:vals[j] for j in range(min(len(names),len(vals)))}
        for k,v in rec.items():
            s=str(v)
            if len(s)>40: s=s[:40]+"..."
            print("   %s = %s" % (k,s))

inspect("tblwXndSi35hLq8R","商品表(大客商品日更)")
inspect("tblExpIMkbUNESTt","天气表(26年-气温数据)")

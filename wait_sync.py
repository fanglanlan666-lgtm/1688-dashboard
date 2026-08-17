import time, os, subprocess

PROC = 24940
PATH = r"C:/Users/Administrator/WorkBuddy/1688业务/data.js"

def proc_alive():
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {PROC}"],
                             capture_output=True, text=True).stdout
        return str(PROC) in out
    except Exception:
        return True

start = time.time()
while True:
    if not proc_alive():
        size = os.path.getsize(PATH)
        with open(PATH, "rb") as f:
            chunk = f.read(3_000_000)
        has_new = b"DASHBOARD_JST_DAY" in chunk
        has_old = b"DASHBOARD_JST =" in chunk
        if has_new and not has_old:
            print(f"SYNC_DONE size={size}")
        else:
            print(f"PROC_ENDED_INVALID size={size} has_new={has_new} has_old={has_old}")
        break
    if time.time() - start > 1800:
        print("TIMEOUT_WAITING")
        break
    time.sleep(20)

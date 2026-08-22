import os, sys
from PIL import Image

TARGET_LONG = 160          # 长边上限(px)：明细表显示仅 42px，留余量防 Retina 模糊
QUALITY = 82
DIRS = [r"C:\Users\Administrator\WorkBuddy\1688业务\images",
        r"C:\Users\Administrator\WorkBuddy\1688业务\发布版\images"]

def compress_one(path):
    try:
        if os.path.getsize(path) < 500:
            return "skip(<500B)"
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            long = max(w, h)
            if long > TARGET_LONG:
                scale = TARGET_LONG / long
                im = im.resize((max(1, int(w*scale)), max(1, int(h*scale))), Image.LANCZOS)
            im.save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        return "ok"
    except Exception as e:
        return f"ERR:{e}"

total_before = total_after = 0
cnt = 0
for d in DIRS:
    if not os.path.isdir(d):
        print("跳过不存在目录:", d); continue
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        p = os.path.join(d, fn)
        before = os.path.getsize(p)
        r = compress_one(p)
        after = os.path.getsize(p)
        total_before += before; total_after += after; cnt += 1
        if cnt % 40 == 0 or r.startswith("ERR"):
            print(f"  {fn}: {before/1024:.0f}KB -> {after/1024:.0f}KB  [{r}]")

print(f"\n完成：共 {cnt} 张")
print(f"压缩前总大小: {total_before/1024/1024:.2f} MB")
print(f"压缩后总大小: {total_after/1024/1024:.2f} MB")
print(f"降幅: {(1-total_after/total_before)*100:.1f}%")

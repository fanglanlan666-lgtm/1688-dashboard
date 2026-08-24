import os, sys
from PIL import Image

TARGET_LONG = 160   # 长边上限(px)：明细表仅 42px 显示，留余量防 Retina
QUALITY = 82

def main():
    d = sys.argv[1]
    if not os.path.isdir(d):
        print("目录不存在:", d); sys.exit(1)
    tb = ta = 0.0; n = 0; err = 0
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        p = os.path.join(d, fn)
        b = os.path.getsize(p)
        if b < 500:
            continue
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                if max(w, h) > TARGET_LONG:
                    s = TARGET_LONG / float(max(w, h))
                    im = im.resize((max(1, int(w*s)), max(1, int(h*s))), Image.LANCZOS)
                im.save(p, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            a = os.path.getsize(p); tb += b; ta += a; n += 1
        except Exception as e:
            err += 1
            print("ERR", fn, e)
    print(f"压缩 {n} 张(失败{err}): {tb/1024/1024:.1f}MB -> {ta/1024/1024:.1f}MB 降幅{(1-ta/tb)*100:.1f}%")

if __name__ == "__main__":
    main()

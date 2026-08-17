#!/bin/bash
# ============================================================
# 1688 数字营销工作台 · 云服务器一键初始化
# 在云服务器 122.152.204.220 上执行： bash setup_cloud.sh
# 作用：生成云服务器密钥(①) + 克隆仓库/恢复.env(②)
#       + 安装依赖/启动(③) + 定时自动同步(④)
# ============================================================

# ---------- 可配置项（按需修改） ----------
# 旧 server_cloud.js 所在目录（用于拷贝原 .env 飞书密钥）。
# 若不知道，先 ssh 登录云服务器 `ps aux | grep server_cloud` 看路径。
OLD_DIR="${OLD_DIR:-/opt/1688-dashboard-old}"
# 新仓库目录
NEW_DIR="/opt/1688-dashboard"
REPO="git@github.com:fanglanlan666-lgtm/1688-dashboard.git"
# ------------------------------------------

echo "===== ① 生成云服务器 SSH 密钥（已存在则跳过） ====="
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
  ssh-keygen -t ed25519 -C "cloud-1688-dashboard" -N ""
fi
echo "请将下面这行【公钥】加到 GitHub 仓库的 Deploy Keys（只读，不要勾 Allow write）："
echo "------------------------------------------------------------"
cat "$HOME/.ssh/id_ed25519.pub"
echo "------------------------------------------------------------"
echo "（GitHub 路径：仓库 → Settings → Deploy keys → Add deploy key → 粘贴 → Add）"
echo "添加完成后，回到这里按回车继续..."
read -r _

echo "===== ② 安装 git / python 并克隆仓库 ====="
if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=; fi
$SUDO apt-get update -y >/dev/null 2>&1 || true
$SUDO apt-get install -y git python3-pip >/dev/null 2>&1 || true

rm -rf "$NEW_DIR"
git clone "$REPO" "$NEW_DIR"

# 恢复飞书密钥 .env（不入库，必须手动/从旧目录拷贝）
if [ -f "$OLD_DIR/.env" ]; then
  cp "$OLD_DIR/.env" "$NEW_DIR/.env"
  echo "已从 $OLD_DIR/.env 复制飞书密钥 ✅"
else
  echo "未找到旧 .env，已生成模板，请填入真实值："
  cat > "$NEW_DIR/.env" <<'EOF'
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BASE_URL=https://open.feishu.cn
EOF
  echo "请编辑 $NEW_DIR/.env 填入 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BASE_URL"
  ${EDITOR:-vi} "$NEW_DIR/.env"
fi

echo "===== 安装依赖（openpyxl 供 sync_feishu.py 使用） ====="
python3 -m pip install --quiet openpyxl 2>&1 | tail -2 || pip install --quiet openpyxl 2>&1 | tail -2

echo "===== ③ 停掉旧进程，用新目录启动 server_cloud.js ====="
pkill -f server_cloud.js || true
sleep 1
cd "$NEW_DIR"
nohup node server_cloud.js > server.log 2>&1 &
sleep 2
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8788/ || echo 000)
echo "本机 8788 自检 HTTP = $CODE （外部用 http://122.152.204.220:8788/ 访问）"

echo "===== ④ 设定时自动同步（每 6 小时 git pull + 重启） ====="
cat > "$NEW_DIR/auto_pull.sh" <<'EOF'
#!/bin/bash
cd /opt/1688-dashboard
git pull --ff-only
pkill -f server_cloud.js
nohup node server_cloud.js > server.log 2>&1 &
EOF
chmod +x "$NEW_DIR/auto_pull.sh"
( crontab -l 2>/dev/null | grep -v "auto_pull.sh"; echo "0 */6 * * * $NEW_DIR/auto_pull.sh >> $NEW_DIR/auto_pull.log 2>&1" ) | crontab -
echo "cron 已设置：每 6 小时自动同步并重启 ✅"
echo ""
echo "全部完成 🎉  以后我优化模块并推到 GitHub，云服务器会自动跟上。"

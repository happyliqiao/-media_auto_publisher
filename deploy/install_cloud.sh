#!/usr/bin/env bash
# 云服务器（Debian / Ubuntu）一键安装脚本
#
#   bash deploy/install_cloud.sh
#
# 环境变量：
#   REPO       仓库地址，默认 https://github.com/happyliqiao/-media_auto_publisher.git
#   APP_DIR    安装目录，默认 ~/media_auto_publisher
#   DRY_RUN    true=只生成不发布（默认），false=真实发布
set -euo pipefail

REPO="${REPO:-https://github.com/happyliqiao/-media_auto_publisher.git}"
APP_DIR="${APP_DIR:-$HOME/media_auto_publisher}"
DRY_RUN="${DRY_RUN:-true}"
APP_USER="$(id -un)"

echo "==> 安装系统依赖"
sudo apt-get update
sudo apt-get install -y \
  git ca-certificates \
  python3 python3-venv python3-pip \
  xvfb x11vnc fluxbox novnc websockify

echo "==> 拉取代码到 $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi

echo "==> 创建虚拟环境并安装依赖"
cd "$APP_DIR"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt
./.venv/bin/playwright install --with-deps chromium

echo "==> 初始化配置"
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "    已生成 config.json，按需修改 platforms.toutiao.options"
fi

echo "==> 生成 VNC 访问密码"
mkdir -p "$HOME/.vnc"
if [ ! -f "$HOME/.vnc/passwd" ]; then
  VNC_PASS="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 12)"
  x11vnc -storepasswd "$VNC_PASS" "$HOME/.vnc/passwd" >/dev/null 2>&1
  echo "$VNC_PASS" > "$HOME/.vnc/passwd.txt"
  chmod 600 "$HOME/.vnc/passwd" "$HOME/.vnc/passwd.txt"
fi

echo "==> 安装 systemd 服务"
sudo mkdir -p /etc/systemd/system
for unit in xvfb fluxbox x11vnc novnc; do
  sudo cp "deploy/systemd/${unit}.service" /etc/systemd/system/
done
sudo cp deploy/systemd/media-auto-publisher.service /etc/systemd/system/
sudo sed -i "s#__APP_USER__#${APP_USER}#g; s#__APP_DIR__#${APP_DIR}#g; s#__DRY_RUN__#${DRY_RUN}#g" \
  /etc/systemd/system/media-auto-publisher.service

sudo systemctl daemon-reload
for unit in xvfb fluxbox x11vnc novnc media-auto-publisher; do
  sudo systemctl enable --now "${unit}.service" || true
done

echo "==> 安装完成"
echo ""
echo "常用命令："
echo "  查看日志   sudo journalctl -u media-auto-publisher -f"
echo "  停止服务   sudo systemctl stop media-auto-publisher"
echo "  改 DRY_RUN 后重载： sudo sed -i 's/MAP_DRY_RUN=.*/MAP_DRY_RUN=false/' /etc/systemd/system/media-auto-publisher.service && sudo systemctl daemon-reload && sudo systemctl restart media-auto-publisher"
echo ""
echo "首次登录今日头条（人工一次）："
echo "  1) 浏览器打开 http://<服务器IP>:6080/vnc.html"
echo "     VNC 密码： $(cat "$HOME/.vnc/passwd.txt" 2>/dev/null || echo '见 ~/.vnc/passwd.txt')"
echo "  2) 服务器上执行： cd $APP_DIR && DISPLAY=:99 ./.venv/bin/python toutiao_browser.py authorize"
echo "  3) 在 VNC 画面里完成扫码/验证码，登录态会存进 $APP_DIR/browser_state/toutiao"
echo ""
echo "提示：登录完成后可以停掉 VNC 暴露面： sudo systemctl stop novnc x11vnc"

#!/usr/bin/env bash
# 开关「真实发布」：同时改 systemd 的 MAP_DRY_RUN 与 config.json 里的平台开关
#
#   bash deploy/enable_publish.sh on     # 开启真实发布
#   bash deploy/enable_publish.sh off    # 回到只生成不发布
set -euo pipefail

MODE="${1:-on}"
APP_DIR="${APP_DIR:-$HOME/media_auto_publisher}"
SERVICE=/etc/systemd/system/media-auto-publisher.service

case "$MODE" in
  on)  DRY_RUN=false ;;
  off) DRY_RUN=true ;;
  *) echo "用法: bash deploy/enable_publish.sh [on|off]" >&2; exit 1 ;;
esac

echo "==> 更新 config.json"
APP_DIR="$APP_DIR" DRY_RUN="$DRY_RUN" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["APP_DIR"]) / "config.json"
cfg = json.loads(path.read_text(encoding="utf-8"))
dry_run = os.environ["DRY_RUN"].strip().lower() in {"1", "true", "yes", "on"}
cfg["dry_run"] = dry_run
cfg.setdefault("platforms", {}).setdefault("toutiao", {})["enabled"] = not dry_run
path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"    dry_run={cfg['dry_run']} toutiao.enabled={cfg['platforms']['toutiao']['enabled']}")
PY

echo "==> 更新 systemd 服务"
sudo sed -i "s/^Environment=MAP_DRY_RUN=.*/Environment=MAP_DRY_RUN=${DRY_RUN}/" "$SERVICE"
sudo systemctl daemon-reload
sudo systemctl restart media-auto-publisher

echo "==> 完成，当前 MAP_DRY_RUN=${DRY_RUN}"
echo "    查看日志: sudo journalctl -u media-auto-publisher -f"

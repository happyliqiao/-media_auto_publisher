# 云端部署指南

目标：**电脑不用开机**，云端自动生成文案并按时发布。

整套系统拆成两段，因为两段的技术要求完全不同：

| 环节 | 能否纯 GitHub Actions | 原因 |
|---|---|---|
| 生成文案 + 审核 + 存档 | ✅ 能，免费 | 纯 Python，无需浏览器 |
| 今日头条自动发布 | ❌ 不能 | 需要**持久化的登录会话** + 有头浏览器 + 规避风控 |

GitHub Actions 的 runner 是临时的（每次重新拉起、IP 是数据中心地址），无法保存头条登录态，也几乎必然被风控拦截。
所以「发布」这一段必须有一台**常开的机器**——最便宜的选择是国内轻量云服务器（2 核 2G，约 ¥60–90/月）。

---

## 方案 A：全托管云服务器（推荐，发布也自动）

### 1. 买一台轻量服务器

推荐阿里云 / 腾讯云轻量应用服务器，Debian 12 或 Ubuntu 22.04，2 核 2G。
选**国内节点**（头条对海外 IP 更敏感）。开发测试期可选按量计费或最便宜的套餐。

### 2. 装依赖、部署服务

```bash
# 本地或服务器上执行
git clone https://github.com/happyliqiao/-media_auto_publisher.git
cd -media_auto_publisher
bash deploy/install_cloud.sh
```

脚本会完成：装系统依赖 → 建 venv → 装 Playwright + Chromium → 建 systemd 服务 → 开机自启。

### 3. 人工登录一次头条（关键，只需一次）

```bash
# 服务器上执行
cd ~/media_auto_publisher
DISPLAY=:99 ./.venv/bin/python toutiao_browser.py authorize
```

同时在你自己电脑的浏览器里打开 `http://<服务器IP>:6080/vnc.html`（密码见 `~/.vnc/passwd.txt`），
就能看到服务器上的浏览器画面，在画面里完成扫码 / 验证码。

登录态保存在 `~/media_auto_publisher/browser_state/toutiao`，**重启服务器不丢**。

> 登录完成后建议收掉 VNC 暴露面：
> `sudo systemctl stop novnc x11vnc`（需要重新登录时再 `start` 即可）

### 4. 打开真实发布

```bash
sudo sed -i 's/MAP_DRY_RUN=.*/MAP_DRY_RUN=false/' /etc/systemd/system/media-auto-publisher.service
sudo systemctl daemon-reload && sudo systemctl restart media-auto-publisher
```

同时把 `config.json` 里的 `platforms.toutiao.enabled` 改成 `true`。

### 5. 日常维护

```bash
sudo journalctl -u media-auto-publisher -f     # 看日志
sudo systemctl restart media-auto-publisher    # 重启
git -C ~/media_auto_publisher pull && sudo systemctl restart media-auto-publisher   # 更新代码
```

---

## 方案 B：只用 GitHub Actions（免费，但不自动发布）

`.github/workflows/generate.yml` 已配置好：每 3 小时在 GitHub 云端生成一篇文案，
结果写入 Actions 运行摘要并作为 Artifact 保留 30 天。

- 开启方式：GitHub 仓库 → **Actions** → 找到 `定时生成文案` → 右上角 **Enable workflow**
- 手动触发：同一页面 → **Run workflow**
- 想立刻看结果：把 cron 改成 `*/15 * * * *`（每 15 分钟），测完记得改回去

这个方案的代价是：**生成是自动的，发布还是得人做**（复制到头条后台，或者你再自己接一个发布通道）。

---

## 方案 C：混合（生成在 Actions，发布在云服务器）

如果你想让云服务器只当「发布执行器」，可以把生成也放 Actions：

1. Actions 里设 `MAP_STORAGE_DIR` 指向一个可被服务器拉取的位置（GitHub Artifact / 对象存储）；
2. 服务器的 daemon 改成「只发布队列」模式。

当前代码尚未实现「从远端拉取队列」这一段，如果需要我可以补上。

---

## 各方案的取舍

| | 成本 | 发布自动化 | 备注 |
|---|---|---|---|
| 方案 A 全托管 | ¥60–90/月 | ✅ 完全自动 | 一次人工登录，长期免维护 |
| 方案 B 仅 Actions | 免费 | ❌ 人工 | 适合先验证内容质量 |
| 方案 C 混合 | ¥60–90/月 | ✅ 完全自动 | 服务器更省资源，实现复杂度略高 |

## 注意事项

- 遇到验证码 / 风控必须人工处理，脚本不会也不能绕过。请保留 VNC 通道以便随时接管。
- 服务器 IP 属于数据中心，头条可能对高危行为更敏感，建议先以低频率（`schedule.stages` 调到 6–8 小时）跑一段时间观察。
- `config.json` 不要提交到仓库（已在 .gitignore 中），API Key 之类的敏感信息放环境变量或服务器本地配置。

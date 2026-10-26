# 项目长期记忆 — media_auto_publisher

## 项目定位
自动生成「普通人如何正确、合适地使用 AI 工具」主题的新媒体文案，按计划存档并推送到今日头条 / 微信公众号 / 小红书。
2026-10-26 之前的主题是「OpenAI Codex 与 Claude Code 免费额度推广」，已整体废弃。

## 内容生产约定
- 主题与风格写在 `config.json` 的 `topic` / `content`，不要写死在代码里。
- 文章一律走 5 套模板轮换（`content_generator.TEMPLATES`），避免连续多篇结构雷同。
- 模板选择用「日期+小时」做随机种子：同一小时内重复运行结果稳定，跨小时自动轮换。
- 每篇必须包含 `topic.required_disclaimer`（结尾免责提示），审核器会校验。
- 审核器内置与近期文章的**重复度检测**（字符二元组 Jaccard，阈值 `review.max_similarity` 默认 0.65）。

## 排期约定
- 发布频率在 `config.schedule.stages` 中按周递增：4h → 3h → 2h → 1h；`until_week: 0` 表示兜底档。
- `config.schedule.publish_hours` 控制可发布时段（默认 `[7, 23]`），调度器会自动把越界时间推回窗口内。
- `python main.py plan` 可预览当天全部计划时间点。

## 发布约定
- `dry_run` 默认 true：只生成、存档、写队列，不真实发帖。
- 队列文件在 `storage_dir/_publish_queue/<平台>/`，带 `consumed_at` 字段；已发布/已消费的会被头条脚本跳过。
- 头条发布选项（封面、广告、位置、声明、定时偏移）统一放在 `platforms.toutiao.options`，代码里不再硬编码。
- 浏览器自动化使用独立 Edge profile（`browser_state/toutiao`）+ CDP 9223 端口，登录需人工完成。
- 遇到验证码/风控必须人工处理，不做绕过。

## 工程约定
- `config.json` 在 .gitignore 中（可能含 API Key），仓库只维护 `config.example.json`。
- git 身份用**仓库级**配置：`happyliqiao / happyliqiao@users.noreply.github.com`（全局未设置）。
- 远端：`https://github.com/happyliqiao/-media_auto_publisher.git`，分支 main。
- 依赖：`playwright>=1.40`（仅浏览器自动化需要），`openai` 为可选。

## 云端运行约定（备选，用户 2026-10-26 决定改走本机）
- **最终路线：用户电脑工作时段开着，daemon 到点本机发布**。用户没有服务器，放弃云端方案。
- daemon 每轮生成后自动调用浏览器发布，发布时刻≈排期时间；发布前校验是否在 `publish_hours` 窗口内。
- 云端方案保留在 `deploy/` 与 `.github/workflows/generate.yml`，作为备选，未删除。
- **文案生成**走 GitHub Actions（`.github/workflows/generate.yml`，每 3 小时一次，UTC cron），电脑不用开机。
- **头条自动发布**必须有一台常开的机器：GitHub Actions runner 是临时的、IP 是数据中心地址，存不住登录态也过不了风控。
- 云端方案 = 国内轻量 VPS（2 核 2G，约 ¥60–90/月）+ Xvfb + Playwright Chromium + systemd + noVNC 人工登录一次。
- 部署脚本：`deploy/install_cloud.sh`（一键装依赖/建 venv/装 systemd）；单元在 `deploy/systemd/`。
- 发布开关用 `deploy/enable_publish.sh on|off`，一条命令同时改 systemd 的 `MAP_DRY_RUN` 与 config 的 `platforms.toutiao.enabled`。
- 安装脚本会自动把 `schedule.start_date` 重置为部署当天（否则沿用旧日期会直接跳到高频档）。
- Linux 上头条脚本走 Playwright `launch_persistent_context`（`toutiao_browser.py` 的非 Windows 分支），登录态存 `browser_state/toutiao`。
- 云端用环境变量覆盖本地配置：`MAP_STORAGE_DIR` / `MAP_DRY_RUN` / `MAP_TIMEZONE` / `MAP_PUBLISH_HOURS`。
- 详见 `deploy/README.md`（方案 A 全托管 / 方案 B 仅 Actions / 方案 C 混合）。
- 未过审稿件存入 `storage_dir/_rejected/`，不进入查重基线（`storage.recent_texts` 跳过 `_` 开头的目录）。

## 本机运行约定
- **playwright 装在系统 Python**（`C:\Users\liqiao\AppData\Local\Programs\Python\Python313`），**托管 Python 里没有**。`start_daemon.ps1` 会逐个探测候选解释器是否 `import playwright` 成功，优先用装了的那个，否则发布环节会被静默跳过。
- 浏览器用本机 Microsoft Edge（Windows 分支走 Edge + CDP 9223），不需要额外下载 Chromium。
- 计划任务用 **Interactive 登录主体**（`install_startup_task.ps1`），否则有头浏览器起不来。
- **后台日志必须行缓冲**：`main.py` 里 `sys.stdout.reconfigure(line_buffering=True)` + `start_daemon.ps1` 用 `-u`。否则 stdout 重定向到文件时 Python 块缓冲，日志长时间是空的。
- PowerShell 脚本一律存为 **UTF-8 with BOM**（PS 5.1 读无 BOM 的中文会乱码）。
- `main.py` 命令：`plan` / `run-once` / `daemon` / `next-interval` / `publish-dry-run` / `publish-now --submit` / `enable-publish` / `disable-publish`。
- `enable-publish` 一条命令同时改 `config.json` 的 `dry_run` 与 `platforms.toutiao.enabled`。
- 头条发布模式由 `platforms.toutiao.options.schedule_offset_hours` 决定：`0` = 立即发布，`>0` = 用头条自身定时发布。
- 首次使用必须先 `python toutiao_browser.py authorize` 人工登录一次，登录态存 `browser_state/toutiao`。

## 发布节奏约定
- 当前 `schedule.stages` 为 **6h → 4h → 3h → 2h**（原 4/3/2/1 已下调）。
- 配合 `publish_hours: [7, 23]`，约合每天 3 → 4 → 6 → 8 篇。
- 调频入口在 `config.json` 的 `schedule.stages`；提速前先观察真实账号数据。
- 用户头条账号是**老号**（有一定内容基础），风控压力比新号小。

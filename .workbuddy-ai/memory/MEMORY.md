# 项目长期记忆 — media_auto_publisher

## 项目定位
自动生成「普通人如何正确、合适地使用 AI 工具」主题的新媒体文案，按计划存档并推送到今日头条 / 微信公众号 / 小红书。
2026-10-26 之前的主题是「OpenAI Codex 与 Claude Code 免费额度推广」，已整体废弃。

## 内容生产约定
- 主题与风格写在 `config.json` 的 `topic` / `content`，不要写死在代码里。
- **当前默认 `generation.provider = compose`：完全不需要 API Key。**
  24 个小节随机抽 6 个 + 8 开头 / 8 过渡句 / 8 结尾 / 24 标题，按素材池原顺序排列保证连贯。
  实测连续 60 篇相似度上限 0.55（阈值 0.65），字数 709–869，全部过审。
- **扩素材池时注意**：18 节时相似度上限 0.588，24 节降到 0.550。加过渡句能把字数下限抬到 709。
  改完必须跑 60 篇滑动窗口压测再提交。
- **免费模型（可选）**：`provider` 填 `zhipu`（glm-4-flash 官方免费）/ `siliconflow` /
  `openrouter` / `deepseek` 即可，预设写在 `content_generator.PROVIDER_PRESETS`。
  走标准库 urllib 调 OpenAI 兼容接口，**不要装 `openai` 包**。Key 写进
  `E:\liqiaobac\ai_news_automation\.env`，变量名用各家预设里的 `key_env`。
- `provider = auto` 按 zhipu → siliconflow → openrouter → deepseek 找可用 Key，全失败回退 compose。
- **DeepSeek 余额为 0**（HTTP 402），要用它得先充值。
- 生成时把近期文章标题一起喂给模型，明确要求换角度，避免撞题。
- 每篇必须包含 `topic.required_disclaimer`（结尾免责提示），审核器会校验。
- 审核器内置与近期文章的**重复度检测**（字符二元组 Jaccard，阈值 `review.max_similarity` 默认 0.65）。

## 排期约定
- 发布频率在 `config.schedule.stages` 中按周递增，当前为 **6h → 4h → 3h → 2h**；`until_week: 0` 表示兜底档。
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
- **playwright 装在系统 Python**（`C:\Users\liqiao\AppData\Local\Programs\Python\Python313`），**托管 Python 里没有**。`start_daemon.ps1` 用固定候选列表逐个探测 `import playwright`，优先用装了的那个。
- **浏览器必须用 Playwright `launch_persistent_context`**（Windows 传 `executable_path=Edge`）。独立 `subprocess.Popen` 起的 Edge 会在脚本退出后被回收，CDP 端口随即关闭。登录态存 `browser_state/toutiao`。
- **本机只有 5.9GB 内存**，可用常在 0.2GB。浏览器启动必须带降内存参数（`--disable-gpu --renderer-process-limit=2 --disable-extensions --disable-background-networking --js-flags=--max-old-space-size=512`），否则 Playwright 会 `VirtualAlloc failed`。
- 计划任务用 **Interactive 登录主体**（`install_startup_task.ps1`），否则有头浏览器起不来。
- **计划任务直接执行 `pythonw.exe -u main.py daemon`**（带 `-WorkingDirectory`），
  **不要再经过 PowerShell 启动脚本中转** —— 那条路径在本机环境下会崩溃或卡死。
  `install_startup_task.ps1` 只在注册时探测带 playwright 的解释器并写进任务动作。
- **daemon 自己写日志**：`main.py` 的 `_attach_daemon_log()` 把 stdout/stderr 落到 `logs/daemon.log`（5MB 轮转）。
  `pythonw` 没有控制台，这是唯一能看到运行状态的地方。**PS 里 `Get-Content` 读它会显示乱码，用 Bash 的 cat 看。**
- **单实例锁**：`storage/daemon.lock` 存 pid。判活必须用 `OpenProcess`+`GetExitCodeProcess`，**不能用 `os.kill(pid, 0)`——Windows 上那会真把进程杀掉**。
- daemon 启动时若 `_publish_queue/toutiao/` 有未发布内容，**先补发再等待**，不新生成。
- 发布超时 `timeout=true` 且日志里**没有 `browser_mode` 行** = 卡在启动浏览器，
  先查是否有孤儿 Edge 占着 `browser_state/toutiao` profile 锁（杀掉进程树常留下）。
- PowerShell 脚本一律存为 **UTF-8 with BOM**（PS 5.1 读无 BOM 的中文会乱码）。
- `main.py` 命令：`plan` / `run-once` / `daemon` / `next-interval` / `publish-dry-run` / `publish-now --submit` / `enable-publish` / `disable-publish`。
- `enable-publish` 一条命令同时改 `config.json` 的 `dry_run` 与 `platforms.toutiao.enabled`。
- 头条发布模式由 `platforms.toutiao.options.schedule_offset_hours` 决定：`0` = 立即发布，`>0` = 用头条自身定时发布。
- **登录已过期时**先 `python toutiao_browser.py authorize` 人工登录一次，脚本会自动检测登录态并退出。
- **用工具直接起的 daemon 会被沙箱回收**（子进程随会话结束），验证自动运行必须靠 `Start-ScheduledTask`。

## 本机环境陷阱（2026-10-28 踩过）
- **进程环境里同时存在 `http_proxy`/`HTTP_PROXY`、`https_proxy`/`HTTPS_PROXY`**（值都是 `http://127.0.0.1:53611`）。
  这会让 PS 的环境变量提供程序抛「已添加了具有相同键的项」，`Get-ChildItem Env:` 和
  `Start-Process` 全部失败。**启动脚本一律用 `[System.Diagnostics.Process]::Start`，不要用 `Start-Process`。**
- 计划任务 `AI_Content_AutoPublisher`：AtLogOn + 每 30 分钟看门狗两个触发器。
  项目目录从 `E:\media_auto_publisher` 搬到 `E:\liqiaobac\-media_auto_publisher` 后，
  旧任务的路径失效导致自动运行彻底停摆——**搬目录后必须重跑 `install_startup_task.ps1`**。
- 系统 Python 没有 `tzdata`，`ZoneInfo("Asia/Shanghai")` 会失败；`main.get_timezone()` 有 `timedelta(hours=8)` 回退，别在别处直接用 `ZoneInfo`。

## 头条页面 DOM 事实（2026-10-27 真机验证，勿再猜）
- 标题：`textarea[placeholder*='标题']`；正文：`.ProseMirror`（唯一 contenteditable）。
- 封面/广告是 `.byte-radio`；作品声明是 `.byte-checkbox`（需先点开「作品声明」面板）。
- 发布按钮文案是 **「预览并发布」**（不是「发布」），点完变成「确认发布」，**两步**。
- 登录判据在**创作者后台首页**做（作品管理/创作灵感/收益数据/草稿箱/粉丝数据），发布页没有这些标记。
- **成功判据看接口**：`POST /mp/agw/article/publish` 返回 `code:0` 且 `data.pgc_id` 非 0。页面文案/URL 跳转都不可靠。
- `code:7050 保存失败` 是草稿自动保存失败，与正式发布无关。
- 页面元素要**批量枚举**（一次 evaluate 取全部），逐个 evaluate 会触发重渲染导致超时误判。

## 防重复发布
- 发布指纹库 `storage/published_toutiao.json`，指纹 = sha1(标题+正文前200字)[:16]。
- 发布前查重命中即跳过；结果不确定时也记指纹。删掉指纹即可恢复。
- **调试脚本绝对不能点「确认发布」** —— 2026-10-27 曾因 probe 脚本连点，同一篇发出 3 次。

## 发布节奏约定
- 当前 `schedule.stages` 为 **6h → 4h → 3h → 2h**（原 4/3/2/1 已下调）。
- 配合 `publish_hours: [7, 23]`，约合每天 3 → 4 → 6 → 8 篇。
- 调频入口在 `config.json` 的 `schedule.stages`；提速前先观察真实账号数据。
- 用户头条账号是**老号**（有一定内容基础），风控压力比新号小。
- 账号名「较神666」，19 粉丝，2026-10-27 起内容主题转向「普通人如何正确使用 AI 工具」。
- **主题转向有风险**：历史内容全是旧主题（Codex 免费额度），平台可能判定内容转向/低质。先发一篇观察数据再谈提速。
- 2026-10-27 09:40 已发布《一个提问公式让AI从玩具变工具》（755 字，pgc_id 7701156416396083752）。

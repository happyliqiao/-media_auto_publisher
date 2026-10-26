# Media Auto Publisher

一个按计划自动生成「普通人如何正确使用 AI 工具」主题新媒体文案、并按规定时间发布到今日头条的工作流工具。

核心流程：生成文案 → 审核（含查重） → 按日期存档 → 写入发布队列 → 到约定时间自动发布。

## 当前已实现

- 内容主题：普通人如何**正确、合适**地使用 AI 工具（能帮上什么忙、有哪些边界、怎么问才有效）。
- 5 套文章模板轮换，按「日期+小时」种子选取，避免连续多篇结构雷同。
- 按周递增的发布频率（`schedule.stages`，当前 6h → 4h → 3h → 2 小时）：
  - 第 1 周：每 6 小时 1 篇
  - 第 2 周：每 4 小时 1 篇
  - 第 3 周：每 3 小时 1 篇
  - 第 4 周及以后：每 2 小时 1 篇
- 发布时段控制：`schedule.publish_hours` 默认 `[7, 23]`，避免凌晨发稿。
- 审核：字数、必备词、风险词、免责提示、标题长度，以及与近期内容的**重复度检测**。
- 队列消费标记：已发布/已消费的稿件不会被重复发布。
- 今日头条浏览器自动化：自动填标题正文、勾选封面/广告/声明、点击发布。

## 快速开始（本机运行）

1. 复制配置文件：

```powershell
Copy-Item .\config.example.json .\config.json
```

2. 预览今天的发布排期：

```powershell
python .\main.py plan
```

3. 跑一次生成测试（只生成不发布）：

```powershell
python .\main.py run-once
```

4. 开启真实发布（改 `config.json` 的 `dry_run` 与 `platforms.toutiao.enabled`）：

```powershell
python .\main.py enable-publish
```

5. 人工登录一次今日头条（只需一次，登录态会保存）：

```powershell
python .\toutiao_browser.py authorize
```

6. 启动持续调度（生成 + 到点发布）：

```powershell
python .\main.py daemon
```

后台启动：

```powershell
.\start_daemon.ps1
```

注册为 Windows 登录后自动启动（用交互式登录模式，保证浏览器能弹出来）：

```powershell
.\install_startup_task.ps1
```

## 命令一览

| 命令 | 作用 |
|---|---|
| `python main.py plan` | 预览当天所有计划发布时刻 |
| `python main.py run-once` | 生成 + 审核 + 存档 + 写队列 |
| `python main.py daemon` | 常驻循环：到点生成并自动发布 |
| `python main.py next-interval` | 看下一次触发时间 |
| `python main.py publish-dry-run` | 手动把最新队列填进头条页面但不点发布 |
| `python main.py publish-now --submit` | 手动发一篇（真实点击发布） |
| `python main.py enable-publish` | 开启真实发布 |
| `python main.py disable-publish` | 回到只生成不发布 |

## 今日头条自动化说明

发布选项（封面、广告、位置、声明、定时偏移）已从代码硬编码改为读取 `platforms.toutiao.options`。

- `schedule_offset_hours: 0` → 生成后**立即发布**（默认，发布时间≈排期时间）
- `schedule_offset_hours: 1` → 用头条自身的「定时发布」，推迟 1 小时上线

`location` 留空表示不设置位置。位置、封面等都属于可选运营策略，按需在 `config.json` 里调。

`publish-latest` / `publish-now` 会跳过已完成（已发布/已消费）的队列文件，避免重复发布。

## 依赖

- 必需：Python 3.10+（只用标准库即可完成生成、审核、存档）
- 发布所需：`playwright`（`pip install -r requirements.txt`）。浏览器用的是本机 Microsoft Edge，不需要额外下载 Chromium。

> `start_daemon.ps1` 会自动挑选**已安装 playwright 的** Python 解释器，避免选错导致发布环节被跳过。

## 使用 OpenAI 生成内容

默认使用本地模板生成，不需要联网。若要使用 OpenAI API：

1. 把 `config.json` 里的 `generation.provider` 改为 `openai`。
2. 设置环境变量 `OPENAI_API_KEY`。
3. 安装依赖：`python -m pip install openai`。

## 合规提醒

本工具聚焦「普通人如何正确使用 AI 工具」的科普与经验分享，不鼓励夸大、诱导或承诺收益类表述。请遵循各平台的内容与自动化规则，不要做绕过验证码、风控或平台限制的操作。遇验证码需要人工在弹出的浏览器窗口里处理。

## 云端运行（备选方案）

若以后想彻底摆脱本地电脑：

- **文案生成**：`GitHub Actions → 定时生成文案` 工作流已内置，每 3 小时在云端跑一次。首次使用需在 Actions 页面点一次 **Enable workflow**。
- **头条自动发布**：需要一台常开的云服务器（持久化登录会话 + 有头浏览器），一键脚本见 [`deploy/README.md`](deploy/README.md)。

环境变量（云端覆盖本地路径）：

| 变量 | 作用 |
|---|---|
| `MAP_STORAGE_DIR` | 存档目录，云端一般设为工作区下的 `_output` |
| `MAP_DRY_RUN` | `true` 只生成不发布，`false` 真实发布 |
| `MAP_TIMEZONE` | 时区，默认 `Asia/Shanghai` |
| `MAP_PUBLISH_HOURS` | 临时覆盖发布时段，如 `7,23` |

## 文件结构

- `main.py`：命令入口（run-once / daemon / plan / publish-* / enable-publish）
- `scheduler.py`：发布频率与时段计算
- `content_generator.py`：文案生成（模板 + OpenAI）
- `reviewer.py`：文案审核（含重复度检测）
- `storage.py`：按时间保存文案并提供近期内容读取
- `publishers.py`：发布适配器与队列
- `toutiao_browser.py` / `run_toutiao_full_publish.py`：今日头条浏览器自动化
- `start_daemon.ps1` / `install_startup_task.ps1`：Windows 后台启动与开机自启
- `.github/workflows/generate.yml`：云端定时生成工作流
- `deploy/`：云服务器一键部署脚本与 systemd 单元
- `config.example.json`：配置模板

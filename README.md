# Media Auto Publisher

一个按计划自动生成「普通人如何正确使用 AI 工具」主题新媒体文案、并按规定时间发布的工作流工具。

核心流程不变：本地（或调用大模型）生成文案 → 基础审核 → 按日期存档 → 写入发布队列 → 到站点的约定时间发布。

## 当前已实现

- 内容主题：普通人如何**正确、合适**地使用 AI 工具（能帮上什么忙、有哪些边界、怎么问才有效）。
- 多套文章模板轮换，避免连续多篇内容雷同（按「日期+小时」种子稳定选取模板与场景）。
- 按周递增的发布频率（可在 `schedule.stages` 调整）：
  - 第 1 周：每 4 小时 1 篇
  - 第 2 周：每 3 小时 1 篇
  - 第 3 周：每 2 小时 1 篇
  - 第 4 周及以后：每 1 小时 1 篇
- 发布时段控制：`schedule.publish_hours` 默认 `[7, 23]`，避免凌晨发稿。
- 每篇内容按日期/时间戳保存到 `storage_dir`（默认 `E:\AI_Content_AutoPublish`）。
- 审核：`min_chars`/`max_chars`、必备词、风险词、免责提示、标题长度，以及与近期内容的**重复度检测**。
- 支持 `dry_run`，先生成、存档、写队列，不真实发布。
- 今日头条、微信公众号、小红书发布适配器（头条支持浏览器自动化）。

## 快速开始

1. 复制配置文件：

```powershell
Copy-Item .\config.example.json .\config.json
```

2. 预览今天的发布排期：

```powershell
python .\main.py plan
```

3. 运行一次生成测试：

```powershell
python .\main.py run-once
```

4. 启动持续调度：

```powershell
python .\main.py daemon
```

后台启动：

```powershell
.\start_daemon.ps1
```

注册为 Windows 登录后自动启动：

```powershell
.\install_startup_task.ps1
```

## 使用 OpenAI 生成内容

默认使用本地模板生成，不需要联网。若要使用 OpenAI API：

1. 把 `config.json` 里的 `generation.provider` 改为 `openai`。
2. 设置环境变量 `OPENAI_API_KEY`。
3. 安装依赖：`python -m pip install openai`。

## 自动发布说明

平台发布默认关闭，并且 `dry_run` 默认为 `true`。工具会生成内容、保存内容、写入发布队列，但不会真实发帖。

真实发布需要满足平台规则：

- 微信公众号：使用官方接口，配置 `app_id_env`/`app_secret_env` 与接口权限。
- 今日头条：通过浏览器自动化操作创作者后台，使用你已授权的登录会话；遇到验证码或风控必须人工处理。
- 小红书：公开自动发布接口能力有限，建议先使用人工确认队列。

## 今日头条浏览器自动化

头条的发布选项（封面、广告、位置、声明、定时偏移）已从代码硬编码改为读取 `platforms.toutiao.options` 配置。

打开可见浏览器并登录：

```powershell
python .\toutiao_browser.py authorize
```

把最新队列内容填入今日头条发布页，但不点击发布：

```powershell
python .\toutiao_browser.py publish-latest
```

确认页面内容无误后，真实点击发布：

```powershell
python .\toutiao_browser.py publish-latest --submit
```

`publish-latest` 会跳过已完成（已发布/已消费）的队列文件，避免重复发布。

## 合规提醒

本工具聚焦「普通人如何正确使用 AI 工具」的科普与经验分享，不鼓励夸大、诱导或承诺收益类表述。请遵循各平台的内容与自动化规则，不要做绕过验证码、风控或平台限制的操作。

## 文件结构

- `main.py`：命令入口（run-once / daemon / next-interval / plan）
- `scheduler.py`：发布频率与时段计算
- `content_generator.py`：文案生成（模板 + OpenAI）
- `reviewer.py`：文案审核（含重复度检测）
- `storage.py`：按时间保存文案并提供近期内容读取
- `publishers.py`：发布适配器与队列
- `toutiao_browser.py` / `run_toutiao_full_publish.py`：今日头条浏览器自动化
- `config.example.json`：配置模板

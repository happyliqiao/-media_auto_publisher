# Media Auto Publisher

这个工具用于按计划生成关于 OpenAI Codex 和 Claude Code 的新媒体文案，保存到 E 盘，并在配置发布通道后推送到平台。

## 当前已实现

- 按周动态计算发布频率：
  - 第 1 周：每 4 小时 1 篇
  - 第 2 周：每 3 小时 1 篇
  - 第 3 周：每 2 小时 1 篇
  - 第 4 周及以后：每 1 小时 1 篇
- 每篇内容按日期和时间戳保存到 `E:\AI_Content_AutoPublish`
- 自动做基础内容检查：长度、必备词、违规/高风险表述
- 支持 dry-run，先生成和保存，不真实发布
- 预留今日头条、微信公众号、小红书发布适配器

## 快速开始

1. 复制配置文件：

```powershell
Copy-Item .\config.example.json .\config.json
```

2. 运行一次生成测试：

```powershell
python .\main.py run-once
```

3. 启动持续调度：

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

## 使用 OpenAI API 生成内容

默认使用本地模板生成，不需要联网。若要使用 OpenAI API：

1. 把 `config.json` 里的 `generation.provider` 改为 `openai`。
2. 设置环境变量：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

3. 运行：

```powershell
python .\main.py run-once
```

首次使用 OpenAI 生成可能需要安装依赖：

```powershell
python -m pip install openai
```

## 自动发布说明

平台发布默认关闭，并且 `dry_run` 默认为 `true`。这意味着工具会生成内容、保存内容、记录发布任务，但不会真实发帖。

真实发布需要满足平台规则：

- 微信公众号：建议使用微信公众平台官方 API，并配置公众号 `AppID`、`AppSecret` 和接口权限。
- 今日头条：建议使用平台官方创作者/开放接口。网页自动化只能使用你已授权的登录会话，遇到验证码或风控必须人工处理。
- 小红书：公开自动发布接口能力有限，建议先使用人工确认队列；不要做绕过验证码、风控或平台限制的自动化。

## 今日头条授权测试

打开可见浏览器并登录：

```powershell
python .\toutiao_browser.py authorize
```

生成一篇内容并写入今日头条待发布队列：

```powershell
python .\main.py run-once
```

把最新队列内容填入今日头条发布页，但不点击发布：

```powershell
python .\toutiao_browser.py publish-latest
```

确认页面内容无误后，真实点击发布：

```powershell
python .\toutiao_browser.py publish-latest --submit
```

## 文件结构

- `main.py`：命令入口
- `scheduler.py`：定时频率计算
- `content_generator.py`：文案生成
- `reviewer.py`：文案检查
- `storage.py`：按时间保存文案
- `publishers.py`：发布适配器
- `config.example.json`：配置模板

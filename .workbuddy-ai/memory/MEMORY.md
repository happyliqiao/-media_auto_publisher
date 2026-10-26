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

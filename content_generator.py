import os
import random


ANGLES = [
    "一个月免费额度别乱用",
    "程序员最容易忽略的 AI 编程红利",
    "Codex 和 Claude Code 到底强在哪",
    "把 AI 编程助手用出真实产出",
    "新手也能看懂的 AI 编程工具攻略",
    "免费试用期最值得测试的能力",
]

SCENARIOS = [
    "阅读陌生项目并快速梳理结构",
    "把需求拆成任务并生成可执行代码",
    "定位报错、补测试、解释复杂逻辑",
    "重构旧代码并保持原有行为稳定",
    "生成脚本、SQL、接口示例和技术文档",
    "辅助学习新框架和新语言",
]


class ContentGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, now):
        provider = self.config.get("generation", {}).get("provider", "template")
        if provider == "openai":
            return self._generate_with_openai(now)
        return self._generate_with_template(now)

    def _generate_with_openai(self, now):
        api_key_env = self.config.get("generation", {}).get("openai_api_key_env", "OPENAI_API_KEY")
        if not os.getenv(api_key_env):
            raise RuntimeError(f"未设置环境变量 {api_key_env}")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("缺少 openai 依赖，请运行 python -m pip install openai") from exc

        client = OpenAI(api_key=os.getenv(api_key_env))
        model = self.config.get("content", {}).get("openai_model", "gpt-5.1")
        campaign_url = self.config.get("content", {}).get("campaign_url", "")
        disclaimer = self.config["topic"]["required_disclaimer"]

        prompt = f"""
请生成一篇适合今日头条、微信公众号、小红书二次改写发布的新媒体中文文案。
主题：OpenAI Codex 与 Claude Code 的功能、作用、适用场景，以及免费获取一个月使用额度。
要求：
1. 700-1400 字。
2. 标题必须 30 个汉字以内，要有点击欲，但不能虚假夸大。
3. 必须包含 OpenAI Codex、Claude Code、免费、一个月。
4. 语言要更像今日头条爆款科普：开头抓人、短段落、强场景、少说教。
5. 活动链接如果为空就不要硬写链接。活动链接：{campaign_url}
6. 不承诺一定可领取，不写破解、绕过、内部渠道。
7. 结尾自然加入提示：{disclaimer}
8. 输出 Markdown，包含标题、正文、小标题、结尾行动建议。
9. 不要在正文底部输出生成时间或时间戳。
"""
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        return response.output_text

    def _generate_with_template(self, now):
        angle = random.choice(ANGLES)
        scenario = random.choice(SCENARIOS)
        campaign_url = self.config.get("content", {}).get("campaign_url", "")
        disclaimer = self.config["topic"]["required_disclaimer"]
        link_line = f"\n\n领取入口：{campaign_url}" if campaign_url else ""
        title = random.choice([
            "AI编程免费一个月怎么用",
            "Codex和Claude别乱试",
            "程序员别错过这波免费额度",
            "AI写代码真的能省时间吗",
            "免费试用AI编程工具指南",
        ])

        return f"""# {title}

这两天很多人都在问同一个问题：OpenAI Codex 和 Claude Code 到底值不值得试？如果还有免费一个月额度，普通人应该怎么玩，才不是白白点开看个热闹？

我的建议很直接：别把它们当“聊天工具”，要当成能进项目、能看代码、能帮你拆任务的 AI 编程搭子。

## 先说结论

OpenAI Codex 更适合放进真实项目里测。你可以让它读项目结构、找关键文件、解释报错、补测试、改脚本，甚至把一个小需求拆成几步执行。它最有价值的地方，不是写一段漂亮代码，而是帮你把“想法到落地”的时间压短。

Claude Code 更像一个耐心的代码分析搭档。遇到长文件、复杂逻辑、陌生项目时，它适合帮你梳理上下文、解释代码意图、对比实现方案，再把任务一步步推进。

## 免费一个月，别这样浪费

很多人拿到免费额度后，第一句就是“帮我写个网站”。这当然能试，但很容易试不出差距。

更好的方法是拿一个真实任务：比如{scenario}。让 AI 先读上下文，再给方案，再改代码，最后让它补测试或写说明。这样你才能看出来，它到底只是会生成文本，还是能真正参与开发流程。

第一周可以测试基础能力：解释代码、生成函数、写脚本、改小 bug。

第二周可以拿一个真实项目，让 OpenAI Codex 或 Claude Code 做一个小功能，从需求拆解到代码修改都跑一遍。

第三周重点测调试和重构。把报错、日志、相关文件给它，看它能不能定位原因，能不能提出可执行的修改建议。

第四周就很现实了：总结它帮你省了哪些时间。如果只是偶尔问两句，那价值有限；如果它能稳定帮你少查资料、少踩坑、少重复劳动，那就值得继续用下去。

## 谁最适合现在就试？

第一类是程序员。你每天都要读代码、改代码、排错，AI 编程工具能不能提效，几天就能看出来。

第二类是正在学编程的人。OpenAI Codex 和 Claude Code 可以把复杂代码拆开讲，也能给你最小示例，比单纯搜索更连贯。

第三类是做独立产品、自动化脚本、运营工具的人。你不一定要成为专业工程师，但可以用 AI 把很多重复工具先做出来。

## 最后提醒

这波免费一个月额度，真正值得关注的不是“免费”两个字，而是你能不能用这段时间验证一个问题：AI 编程助手能不能进入你的日常工作流。

如果你只是随便体验，可能很快就忘了；如果你拿真实项目连续测试，很可能会发现，写代码这件事已经开始变了。{link_line}

提示：{disclaimer}
"""

import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent

# 复用的密钥文件（ai_news_automation 项目里已配好）
DEFAULT_ENV_FILE = r"E:\liqiaobac\ai_news_automation\.env"


# 免费/低价模型预设。provider 填名字即可，不用记 base_url 和 model。
PROVIDER_PRESETS = {
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
        "note": "按量付费，无免费额度",
    },
    "zhipu": {
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "key_env": "ZHIPU_API_KEY",
        "note": "glm-4-flash 官方免费，国内直连",
    },
    "siliconflow": {
        "api_base": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "key_env": "SILICONFLOW_API_KEY",
        "note": "注册送额度，部分小模型免费",
    },
    "openrouter": {
        "api_base": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_env": "OPENROUTER_API_KEY",
        "note": "有 :free 模型，但国内需要代理",
    },
}


SCENARIOS = [
    "写周报和工作总结",
    "整理一场两小时的会议记录",
    "查资料之前先列个提纲",
    "改简历和自我介绍",
    "写一段不好开口的沟通话术",
    "把长文章压缩成三条要点",
    "翻译并润色一份外文资料",
    "给孩子讲清楚一个知识点",
    "规划一次家庭旅行",
    "整理一堆零散的客户反馈",
    "做一份简单的数据表格",
    "准备一次汇报的讲稿",
]


# ---------------------------------------------------------------------------
# 组合式素材池：不需要任何 API Key
#
# 一篇文章 = 1 个标题 + 1 个开头 + 5 个小节 + 1 个结尾。
# 18 个小节里随机抽 5 个，组合数约 100 万种，相邻两篇共享的小节很少，
# 字符二元组相似度能稳定压在 0.65 阈值以下。
# ---------------------------------------------------------------------------

TITLES = [
    "用AI没效果，多半是这几个习惯没建立",
    "普通人用AI，先学会把话说清楚",
    "AI用得好的人，都在这几件小事上较真",
    "别再把AI当搜索引擎用了",
    "同一个AI工具，为什么有人用得又快又好",
    "用AI之前，先想清楚这三件事",
    "AI帮不上忙，往往不是工具的问题",
    "普通人用好AI的几条实用经验",
    "把AI当实习生，比当专家管用",
    "AI给的答案不能直接用，原因在这里",
    "用AI省时间的几个具体做法",
    "不追新工具，也能把AI用明白",
    "和AI说话，方式比工具重要",
    "AI用不起来，先检查你的提问方式",
    "普通人用AI的边界在哪里",
    "让AI真正帮上忙的几条经验",
    "AI不是万能，但这两类活它确实强",
    "从没感觉到离不开，中间差了什么",
    "用AI这件事，方法比工具重要",
    "AI能替你做什么，不能替你做什么",
    "普通人上手AI，先避开这几个坑",
    "把要求说具体，AI才给得出好东西",
    "AI用久了才会明白的几件事",
    "别指望AI替你想，但它能帮你想到",
]

OPENINGS = [
    "很多人用 AI 的方式，其实和用搜索引擎差不多：有问题就问一句，答案看着顺眼就复制走。这样用也能省点时间，但对普通人来说，很难真正拉开差距。区别往往不在工具，而在用法。",
    "AI 工具这两年普及得很快，但真正用顺手的普通人并不多。大部分人的问题不是不会操作，而是不知道该怎么提要求。",
    "装了一堆 AI 工具，用几次就放下了，理由是感觉没啥用。这个感受在普通人里很常见，但问题通常不在工具。",
    "同一个 AI 工具，有人几分钟弄完一件事，有人来回折腾半天。对普通人来说，差别不在谁更懂技术，而在几个很具体的习惯上。",
    "不用把 AI 想得太复杂。对普通人来说，它能不能帮上忙，往往取决于你有没有把话说清楚。",
    "身边问我怎么用 AI 的人不少，问得最多的不是用哪个，而是为什么我用不出效果。这大概是普通人最普遍的困惑。",
    "AI 不会让普通人一下子变专家，但它确实能把很多琐事的门槛降下来。前提是用对方式。",
    "关于 AI 的讨论很多，落到普通人身上其实就一个问题：怎么用它，才不至于白折腾。",
]

SECTIONS = [
    {
        "heading": "先说清背景，再提要求",
        "body": "AI 不是读心术。你只说帮我写个总结，它只能给你一个通用模板。补一句这是给部门周会用的，读者是领导和同事，重点讲进展和风险，控制在 300 字，结果会完全不同。\n\n背景、对象、篇幅、语气，这四样说清楚，产出质量立刻上一个台阶。这一步最多花半分钟，省下来的却是半小时的修改。",
    },
    {
        "heading": "一次只让它做一件事",
        "body": "不少人喜欢一句话扔十个要求：既要总结，又要润色，还要出三个版本，顺便配个标题。结果每样都做得马马虎虎。\n\n更好的做法是拆开。先让它整理要点，你确认没问题，再让它按要点写正文。每一步都可控，出错也好回退。",
    },
    {
        "heading": "把它当实习生，而不是专家",
        "body": "这个心态很重要。AI 能快速给出一个还不错的初稿，但它不了解你的具体处境，也可能会一本正经地说错。\n\n所以合理的位置是：让它做初稿、做整理、做初筛，你来判断和拍板。凡是涉及数字、结论、对外发布的内容，都要自己再核一遍。",
    },
    {
        "heading": "给它一个参照物",
        "body": "比起空口描述，直接给例子效果好得多。想让它写出你想要的风格，就贴一段你觉得好的文字，说按这个语气来。想让它整理表格，就把表头贴给它。\n\n有样板，它就不用猜。这条比记住几十个提示词模板都管用。",
    },
    {
        "heading": "数字和引用，必须自己核",
        "body": "大模型有个特点：它很擅长把不确定的东西说得像确定的一样。数据、条款、引用来源，都可能出现看似合理实则错误的内容。\n\n所以有个简单原则：凡是能被查证的事实，都去查一遍；凡是涉及钱、健康、法律的建议，都别直接照做。",
    },
    {
        "heading": "别把隐私信息贴进去",
        "body": "身份证号、银行卡、家庭住址、公司内部资料，这些能脱敏就脱敏。\n\n需要它处理的时候，用占位符代替真实信息，比如张某某、某公司、一万多元。它照样能理解结构，你也少了一层风险。",
    },
    {
        "heading": "追问比一次问对更现实",
        "body": "第一版不满意，别急着放弃，也别从头重写。直接说第二段太啰嗦，压到两句；换个更口语的说法；这个例子不合适，换成工作场景的。\n\n多轮对话往往比一次问对更现实。会用 AI 的人，通常不是第一句问得多好，而是后面追得够准。",
    },
    {
        "heading": "让它先列提纲，再写正文",
        "body": "直接让它写长文，很容易写得又空又散。更好的顺序是：先让它给三个不同的提纲，你挑一个，再让它按提纲展开。\n\n提纲阶段改起来成本很低，正文写完再改就费劲了。这个顺序能把返工量降下来一大半。",
    },
    {
        "heading": "把好的标准说具体",
        "body": "写得好一点这种要求，它没法执行。换成少用形容词、每段不超过三句、不要用感叹号、结论放最前面，它立刻就能照做。\n\n你说不清标准，它就只能用平均值应付你。把标准翻译成可检查的规则，是提问里最值钱的一步。",
    },
    {
        "heading": "重要决定别交给它",
        "body": "买房、跳槽、投资、要不要和一个人继续交往，这些事可以让它帮你理清思路、列出选项、分析利弊。\n\n但决定必须你自己下。它不知道你的风险承受能力，也不会为结果负责。把它放在参谋的位置上，别放在决策者的位置上。",
    },
    {
        "heading": "让它解释，而不是替你思考",
        "body": "遇到看不懂的概念，让它用大白话讲一遍，再举个生活里的例子，最后让它出两道题考考你。\n\n这个用法比直接给我答案有价值得多。前者让你真的懂了，后者只是让你暂时不用想。",
    },
    {
        "heading": "建立自己的常用指令库",
        "body": "你会发现有些要求每次都要重复说。把它们存下来，形成自己的模板：周报怎么写、邮件怎么改、会议记录怎么整理。\n\n用久了，你的效率提升主要来自这几条固定指令，而不是每次临场发挥。",
    },
    {
        "heading": "别追新工具，先把一个用熟",
        "body": "AI 产品多到挑不过来，很多人一上来就订阅好几个。\n\n其实对大部分普通人来说，先把一个工具用熟，比同时装五个更有价值。你真正常用的场景可能就那么两三个，把这两三个打磨顺了，再考虑要不要换。",
    },
    {
        "heading": "让它帮你找思路，而不是找答案",
        "body": "卡住的时候，让它列十个方向，哪怕九个不靠谱，剩下那一个也可能点醒你。\n\n这种用法风险最低、收益却不小，因为最终判断还在你手上。把它当陪你想问题的人，比当答题机更划算。",
    },
    {
        "heading": "长文档先压缩，再处理",
        "body": "一份五十页的材料直接丢给它，它很容易抓错重点。\n\n更稳的做法是分段处理：先让它把每一部分压成三条要点，你确认要点没问题，再基于要点做汇总或改写。中间这一步能省掉大量返工。",
    },
    {
        "heading": "让它扮演具体角色",
        "body": "你是一个有十年经验的 HR，比帮我看看简历有效得多。\n\n角色设定等于给它一套判断标准：关注什么、忽略什么、用什么口径说话。角色越具体，输出越贴近你要的东西。",
    },
    {
        "heading": "输出格式要提前约定",
        "body": "最后告诉它你要什么形态的东西：一段话、一个表格、三条要点，还是一个可以直接发出去的版本。\n\n这一步很多人会漏掉，结果拿到一大段文字，还得自己重新排版。提前说清楚格式，能省掉最后那道手工活。",
    },
    {
        "heading": "用完花十秒复盘",
        "body": "每次用完，花十秒钟想一想：哪句话它理解错了？是我表达的问题，还是它确实做不到？\n\n这个动作看起来很小，但坚持一个月，你会明显感觉到自己越来越会提问。会用 AI 的人，本质上不是背了多少提示词，而是清楚一件事该拆成几步。",
    },
    {
        "heading": "把大任务拆成小步骤",
        "body": "一份完整的方案，别指望一次生成。拆成目标、结构、内容、措辞四步，每步单独确认。\n\n中间每一步你都能看出问题，改起来也便宜。一次性要成品，往往只能在最后推倒重来。",
    },
    {
        "heading": "同一个问题，换个问法再试一次",
        "body": "第一遍结果不理想，不一定是它做不到。换一种描述方式，或者从反面问一次，常常能拿到完全不同的东西。\n\n提问本质上是在给约束。约束换了，解空间就变了。",
    },
    {
        "heading": "先要几个版本，再挑一个",
        "body": "让它一次给三个不同风格或不同详略的版本，比反复修改一个版本更高效。\n\n对比着看，你更容易发现自己到底想要什么。这个判断过程本身，也是在帮你把需求想清楚。",
    },
    {
        "heading": "别在它不擅长的领域较劲",
        "body": "有些事它就是做不好，比如精确计算、实时信息、需要专业资质判断的内容。反复调教往往只是浪费时间。\n\n判断标准很简单：这件事有没有明确的正确答案，且这个答案能立刻验证。没有的话，就别指望它。",
    },
    {
        "heading": "把有用的结果存下来",
        "body": "聊出来的好东西，关掉窗口就没了。准备一个自己的文档，把好用的提问、满意的输出存起来。\n\n积累两三个月，你会有一份完全贴合自己工作的资料，比任何通用教程都有用。",
    },
    {
        "heading": "注意它在时间和版本上出错",
        "body": "涉及日期、政策、软件版本、价格的信息，它经常给出过时或者虚构的答案。\n\n这类内容不要直接引用。要用的地方，先去官方渠道核对一遍，再写进去。",
    },
]

TRANSITIONS = [
    "下面这几件事，看起来都不难，但真正做到的人不多。",
    "结合我自己的使用经验，下面几条最值得先练。",
    "具体来说，有几个习惯值得单独拿出来说。",
    "这几年用下来，真正管用的是下面这些做法。",
    "把这几条做到，效果会比换工具明显得多。",
    "下面几点，都是踩过坑之后才想明白的。",
    "说起来都是常识，但很多人第一步就漏了。",
    "不需要全做到，先挑两条试一周就有感觉。",
]

CLOSINGS = [
    "AI 工具更新很快，今天好用的方法，下个月可能就有更省事的方式。但底层那几条不会变：说清需求、拆小步骤、自己把关。普通人不需要追上每一次更新，把这三点变成习惯，就已经比大多数人用得好了。",
    "说到底，AI 改变的不是能不能做，而是愿不愿意开始。很多事以前因为麻烦一直拖着，现在起步成本低了，反而更容易动起来。",
    "不用追求把每个功能都用上。把手上那两三个高频场景用好，知道它哪里靠得住、哪里靠不住，就已经超过大多数人了。",
    "工具只是工具。真正决定效果的，是你有没有想清楚自己要什么。想清楚了，随便一个 AI 都能帮上忙；想不清楚，再贵的订阅也白搭。",
    "这些方法都不难，难的是养成习惯。挑一条这周先试，比收藏一百篇教程管用。",
    "AI 不会替你负责，也不会替你思考。它能做的是把重复劳动压缩掉，把起步的门槛降下来，剩下的还是得你自己来。",
    "如果你现在只用它查资料、写两句客套话，那确实有点浪费。试着把它放进一件你一直嫌麻烦的事里，感受会完全不一样。",
    "不用着急。用 AI 这件事没有标准答案，适合自己的节奏最重要。先从一件小事开始，慢慢就有感觉了。",
]


def _read_env_file(path):
    """从 .env 读取 KEY=VALUE，读不到就返回空字典。"""
    values = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _recent_titles(recent_texts):
    titles = []
    for text in recent_texts:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                titles.append(line[2:].strip())
                break
    return titles


class ContentGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, now, recent_texts=None):
        recent_texts = recent_texts or []
        gen_cfg = self.config.get("generation", {}) or {}
        provider = (gen_cfg.get("provider") or "compose").strip().lower()

        if provider == "compose":
            return self._generate_with_compose(now, recent_texts)

        if provider == "auto":
            for name in ("zhipu", "siliconflow", "openrouter", "deepseek"):
                if not self._has_key(gen_cfg, name):
                    continue
                try:
                    return self._generate_with_llm(now, name, gen_cfg, recent_texts)
                except Exception as exc:
                    print(f"llm_generate_failed provider={name} {exc.__class__.__name__}: {exc}")
            print("fallback=compose")
            return self._generate_with_compose(now, recent_texts)

        try:
            return self._generate_with_llm(now, provider, gen_cfg, recent_texts)
        except Exception as exc:
            print(f"llm_generate_failed provider={provider} {exc.__class__.__name__}: {exc}")
            print("fallback=compose")
            return self._generate_with_compose(now, recent_texts)

    # -- 组合式生成（零依赖、零成本、无需 Key）--------------------------------

    def _next_seq(self):
        path = ROOT / "storage" / "compose_seq.txt"
        try:
            current = int(path.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            current = 0
        current += 1
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(current), encoding="utf-8")
        except OSError:
            pass
        return current

    def _generate_with_compose(self, now, recent_texts):
        seq = self._next_seq()
        rng = random.Random(f"compose-{seq}")

        disclaimer = self.config["topic"]["required_disclaimer"]
        used = set(_recent_titles(recent_texts))

        available = [t for t in TITLES if t not in used] or TITLES
        title = available[seq % len(available)]

        # 随机抽 6 节后按素材池原顺序排列，保证行文逻辑连贯
        picked = sorted(rng.sample(range(len(SECTIONS)), 6))
        opening = rng.choice(OPENINGS)
        transition = rng.choice(TRANSITIONS)
        closing = rng.choice(CLOSINGS)

        parts = [f"# {title}", "", opening, "", transition, ""]
        for index in picked:
            section = SECTIONS[index]
            parts.append(f"## {section['heading']}")
            parts.append("")
            parts.append(section["body"])
            parts.append("")
        parts.append(closing)
        parts.append("")
        parts.append(f"提示：{disclaimer}")

        return "\n".join(parts) + "\n"

    # -- 大模型生成 -----------------------------------------------------------

    def _preset(self, provider):
        return PROVIDER_PRESETS.get(provider, {})

    def _key_env_name(self, gen_cfg, provider):
        return gen_cfg.get("api_key_env") or self._preset(provider).get("key_env")

    def _lookup_key(self, gen_cfg, provider):
        env_name = self._key_env_name(gen_cfg, provider)
        if env_name:
            value = os.getenv(env_name)
            if value:
                return value
        env_file = gen_cfg.get("api_key_file") or DEFAULT_ENV_FILE
        values = _read_env_file(env_file)
        for name in (env_name, gen_cfg.get("api_key_file_env") or "AI_NEWS_API_KEY"):
            if name and values.get(name):
                return values[name]
        return None

    def _has_key(self, gen_cfg, provider):
        return bool(self._lookup_key(gen_cfg, provider))

    def _resolve_api_key(self, gen_cfg, provider):
        key = self._lookup_key(gen_cfg, provider)
        if key:
            return key
        env_name = self._key_env_name(gen_cfg, provider) or "API_KEY"
        env_file = gen_cfg.get("api_key_file") or DEFAULT_ENV_FILE
        raise RuntimeError(f"未找到 {provider} 的 API Key（环境变量 {env_name} 或 {env_file} 中的同名项）")

    def _build_prompt(self, recent_texts):
        content_cfg = self.config.get("content", {}) or {}
        topic = self.config["topic"]["primary"]
        disclaimer = self.config["topic"]["required_disclaimer"]
        style = content_cfg.get("style", "")
        campaign_url = content_cfg.get("campaign_url", "")
        min_chars = int(content_cfg.get("min_chars", 700))
        max_chars = int(content_cfg.get("max_chars", 1600))
        scenario = random.choice(SCENARIOS)

        titles = _recent_titles(recent_texts)[:8]
        avoid = ""
        if titles:
            avoid = "\n6. 下面这些标题已经用过，必须换一个完全不同的切入角度和标题，不要复用：\n" + "\n".join(
                f"   - {title}" for title in titles
            )

        return f"""请写一篇适合今日头条发布的中文文章。

主题：{topic}
风格：{style}

硬性要求：
1. 正文 {min_chars}-{max_chars} 字。
2. 第一行是 Markdown 一级标题，标题不超过 25 个汉字，具体、有信息量，不用夸张疑问句。
3. 正文中必须出现"AI"和"普通人"这两个词。
4. 围绕一个具体场景展开：{scenario}。
5. 有小标题，短段落，开头直接进入内容，不要写"在这个信息爆炸的时代"这类套话。{avoid}
7. 不要出现月入过万、躺赚、包学会、割韭菜、稳赚不赔这类夸大或诱导表述。
8. 结尾另起一行，原样写上：提示：{disclaimer}
9. 只输出 Markdown 正文，不要输出任何解释、前言或生成时间。
10. {"不要写任何网址或推广链接。" if not campaign_url else "活动链接：" + campaign_url}"""

    def _generate_with_llm(self, now, provider, gen_cfg, recent_texts):
        api_key = self._resolve_api_key(gen_cfg, provider)
        preset = self._preset(provider)
        base = (gen_cfg.get("api_base") or preset.get("api_base") or "").rstrip("/")
        model = gen_cfg.get("model") or preset.get("model")
        if not base or not model:
            raise RuntimeError(f"未知 provider={provider}，请在 generation 里显式配置 api_base 与 model")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是中文新媒体编辑，写作克制、具体、有分寸，不写套话。"},
                {"role": "user", "content": self._build_prompt(recent_texts)},
            ],
            "temperature": 1.15,
            "max_tokens": 2400,
        }
        request = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        last_error = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                text = (text or "").strip()
                if not text:
                    raise RuntimeError("模型返回空内容")
                return text + "\n"
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code in (401, 403):
                    break
            except Exception as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt == 0:
                continue
        raise RuntimeError(f"模型调用失败 {last_error}")

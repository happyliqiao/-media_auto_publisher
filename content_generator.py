import json
import os
import random
import urllib.error
import urllib.request


# 复用的密钥文件（ai_news_automation 项目里已配好 DeepSeek 密钥）
DEFAULT_ENV_FILE = r"E:\liqiaobac\ai_news_automation\.env"


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


def _link_block(campaign_url):
    return f"\n\n相关入口：{campaign_url}" if campaign_url else ""


def _checklist(rng, scenario, disclaimer, campaign_url):
    return f"""# 普通人用AI的5个正确姿势

很多人用 AI 工具的方式，其实和用搜索引擎差不多：有问题就问一句，答案看着顺眼就复制走。这样用也能省点时间，但很难真正拉开差距。

拿{scenario}来说就很典型。同一件事，有人几分钟弄完，有人来回折腾半天，区别往往不在工具，而在用法。

下面这 5 个习惯，是普通人最值得先建立起来的。

## 一、先交代背景，再说要什么

AI 不是读心术。你只说"帮我写个总结"，它只能给你一个通用模板；你补一句"这是给部门周会用的，读者是领导和同事，重点讲进展和风险，控制在 300 字"，结果会完全不同。

背景、对象、篇幅、语气，这四样说清楚，产出质量立刻上一个台阶。这一步最多花半分钟，省下来的却是半小时的修改。

## 二、一次只让它做一件事

不少人喜欢一句话扔十个要求：既要总结，又要润色，还要出三个版本，顺便配个标题。结果每样都做得马马虎虎。

更好的做法是拆开。先让它整理要点，你确认没问题，再让它按要点写正文。每一步都可控，出错也好回退。

## 三、把它当实习生，而不是专家

这个心态很重要。AI 能快速给出一个还不错的初稿，但它不了解你的具体处境，也可能会一本正经地说错。

所以合理的位置是：让它做初稿、做整理、做初筛，你来判断和拍板。凡是涉及数字、结论、对外发布的内容，都要自己再核一遍。

## 四、给它一个参照物

比起空口描述，直接给例子效果好得多。想让它写出你想要的风格，就贴一段你觉得好的文字，说"按这个语气来"。想让它整理表格，就把表头贴给它。

有样板，它就不用猜。这条比记住几十个提示词模板更管用。

## 五、养成复盘的习惯

每次用完，花十秒钟想一想：哪句话它理解错了？是我表达的问题，还是它确实做不到？这个动作看起来很小，但坚持一个月，你会明显感觉到自己越来越会提问。

会用 AI 的人，本质上不是背了多少提示词，而是清楚一件事该拆成几步、每步该交代什么。

## 最后

AI 工具更新很快，今天好用的方法，下个月可能就有更省事的方式。但底层那几条不会变：说清需求、拆小步骤、自己把关。

普通人不需要追上每一次更新，把这三点变成习惯，就已经比大多数人用得好了。{_link_block(campaign_url)}

提示：{disclaimer}
"""


def _myths(rng, scenario, disclaimer, campaign_url):
    return f"""# 关于AI工具普通人最常见的4个误解

AI 工具这两年普及得很快，但很多人对它的理解还停留在"很厉害"或者"不靠谱"这两个极端。真正用起来之后会发现，问题往往出在预期上。

下面这 4 个误解，是跟身边人聊下来最常听到的。

## 误解一：有了 AI 就不用学了

这是最容易踩的坑。AI 能帮你写出一段文案、一份报告，但你没法判断它写得好不好，除非你自己懂一点。

它更像是放大器：你懂七分，它能帮你做到九分；你完全不懂，它给你的东西你也没法验证，最后只能全盘接受，风险其实更大。

所以正确的用法不是"不学了"，而是"学得更快"。它省下的是查资料和搭框架的时间，不是思考本身。

## 误解二：问得越短越省事

很多人习惯一句话提问："帮我写个方案。"

结果拿到的东西看着挺长，但基本不能用。因为 AI 不知道你的行业、你的对象、你要解决什么问题，只能给你一个最平均的答案。

多花三十秒交代背景，往往能省掉半小时修改。这笔账怎么算都划算。

## 误解三：AI 说的都是对的

大模型有个特点：它很擅长把不确定的东西说得像确定的一样。数据、条款、引用来源，都可能出现看似合理实则错误的内容。

所以有个简单原则：凡是能被查证的事实，都去查一遍；凡是涉及钱、健康、法律的建议，都别直接照做。

把它当成一个愿意陪你讨论的同事，而不是一个不会出错的权威。

## 误解四：工具越贵越好

现在 AI 产品多到挑不过来，很多人一上来就订阅好几个。

其实对大部分普通人来说，先把一个工具用熟，比同时装五个更有价值。你真正常用的场景可能就那么两三个，比如{scenario}，差不多占了大半。

把这两三个场景打磨顺了，再考虑要不要换工具。

## 换个角度看

AI 不会让普通人一下子变专家，但它确实能把很多琐事的门槛降下来。

关键是想清楚一件事：你希望它替你省时间，还是替你思考？前者很容易做到，后者只能靠你自己。想明白这个，很多纠结就没了。{_link_block(campaign_url)}

提示：{disclaimer}
"""


def _day_in_life(rng, scenario, disclaimer, campaign_url):
    return f"""# 普通人一天里AI到底能帮上什么忙

不用把 AI 想得太宏大。对普通人来说，它最有价值的地方，往往藏在一天里那些琐碎又不得不做的小事上。

我按一天的顺序，说说哪些环节它真能帮上忙。

## 早上：先理清今天要干什么

刚坐下的时候脑子最乱。这时候可以让它帮你把待办过一遍：把今天要做的事列出来，按紧急和重要排个序，标出哪几件必须今天完成。

它排得不一定完美，但能逼你把事情写下来。这个动作本身就值。

## 上午：处理文字类的活

上午精力最好，适合干正事。但正事里总夹着一堆文字活：回邮件、写说明、改材料。

这类事情的特点是格式要求明确、内容不太难，正好是 AI 的强项。像{scenario}，交给它出个初稿，你再改两笔，比从空白页开始快得多。

## 下午：查东西和整理东西

下午容易犯困，适合做不需要太动脑的整理工作。

比如把一堆零散的资料归纳成三条要点，把长文档压缩成一页纸，把表格里的数据按你的要求重新归类。这些事人工做起来枯燥，AI 做得又快又稳。

## 晚上：学点新东西

这个时段最适合用它来学东西。遇到看不懂的概念，可以让它用大白话解释一遍，再举个生活里的例子，最后让它出两道题考考你。

比单纯看资料有效，因为你能立刻知道自己哪里没懂。

## 但有几件事别交给它

第一，别让它替你做重要决定。买房、跳槽、投资，它可以帮你理清思路，但决定得你自己下。

第二，别把隐私信息直接贴进去。身份证号、银行卡、公司内部资料，能脱敏就脱敏。

第三，别用它替代真实沟通。有些话必须自己说，AI 写得再得体，也代替不了你的态度。

## 说到底

AI 工具真正改变的不是"能不能做"，而是"愿不愿意开始"。

很多事以前因为麻烦就一直拖着，现在起步成本低了，反而更容易动起来。这大概是它对普通人最实在的意义。{_link_block(campaign_url)}

提示：{disclaimer}
"""


def _prompt_formula(rng, scenario, disclaimer, campaign_url):
    return f"""# 一个提问公式让AI从玩具变工具

很多人装了 AI 工具，用几次就放下了，理由是"感觉没啥用"。

问题通常不在工具，而在提问方式。问得太笼统，它只能给笼统的答案；问得具体，它才有发挥空间。

这里给一个简单的四段式公式，普通人照着套就行。

## 第一段：交代身份和场景

先说清楚你是谁、在什么情况下用。

比如不要写"帮我写个总结"，而是写"我是做行政的，每周要给部门写工作周报"。这一句话就把语境定住了，它知道该用什么口径。

## 第二段：说清任务和边界

任务要具体到可执行。不要写"帮我优化一下"，而是写"把这段文字压缩到 200 字以内，保留三个关键数据，语气正式一点"。

边界越清楚，返工越少。

## 第三段：给一个参照

如果有现成的样板，直接贴上去。想让它模仿某种风格，就给它一段那种风格的文字；想让它按某个格式输出，就给一个格式示例。

对 AI 来说，一个例子胜过十句描述。

## 第四段：约定输出形式

最后告诉它你要什么形态的东西：一段话、一个表格、三条要点，还是一个可以直接发出去的版本。

这一步很多人会漏掉，结果拿到一大段文字，还得自己重新排版。

## 举个完整的例子

假设你想让它帮忙处理{scenario}这件事：

"我是普通上班族，平时不太擅长写东西。这周要做{scenario}，需要一段 300 字左右的说明，读者是我的直属领导，语气简洁、不要客套。可以参考我上次写的那段（贴一段）。输出直接给我可以用的版本，不要解释。"

这样一段话发过去，拿到的结果通常一次就能用。

## 公式之外的两件事

一是要敢追问。第一版不满意，别急着放弃，直接说"第二段太啰嗦，压到两句"、"换个更口语的说法"。多轮对话往往比一次问对更现实。

二是要留个心眼。它给的数字、条款、引用，都要自己核一遍。公式能提高效率，但不能替你负责。

普通人把这个公式用熟，比收藏一百篇提示词合集都有用。{_link_block(campaign_url)}

提示：{disclaimer}
"""


def _boundary(rng, scenario, disclaimer, campaign_url):
    return f"""# AI能做什么和不该做什么普通人要分清

AI 工具用久了会发现一个规律：它在某些事上强得惊人，在另一些事上又笨得让人着急。

搞清楚这条界线在哪，比学会多少提示词都有用。

## 它擅长的事：有明确标准、可快速验证

第一类是格式转换。把长文压成要点、把要点扩成段落、把一种格式改成另一种，这类活它做得又快又稳。

第二类是初稿生成。从零开始最难，它能先给你一个能改的东西。像{scenario}，有个初稿打底，效率完全不一样。

第三类是解释和翻译。遇到看不懂的内容，让它用大白话讲一遍，或者换个角度再讲一遍，比反复读原文有效。

第四类是找思路。你卡住的时候，让它列十个方向，哪怕九个不靠谱，剩下那一个也可能点醒你。

这四类的共同点是：结果好不好，你自己一眼能判断。

## 它不擅长的事：需要真实判断和承担责任

第一类是事实核查。它可能编出看起来很真的数据、条款、引用。凡是能查的，都去查。

第二类是专业决策。医疗、法律、投资，这些领域错一次的代价太大，不能靠一个概率模型给建议。

第三类是了解你的处境。它不知道你老板的脾气、你团队的暗流、你家里最近发生了什么。这些信息缺失，它给的方案再漂亮也可能不适用。

第四类是替你表达态度。道歉、拒绝、争取，这些话必须自己说。AI 写得太圆滑，反而显得没有诚意。

## 一个简单的判断方法

拿到任务先问自己一句：这个结果如果错了，我能不能立刻发现？

能，就放心交给它；不能，就自己多花点时间把关，或者干脆自己做。

这条线划清楚，用起来会踏实很多。很多对 AI 的失望，其实是把它放到了不合适的位置上。

## 最后

普通人不需要成为 AI 专家，也没必要追每一个新工具。

把手上那两三个高频场景用好，知道它哪里靠得住、哪里靠不住，就已经超过大多数人了。{_link_block(campaign_url)}

提示：{disclaimer}
"""


TEMPLATES = [_checklist, _myths, _day_in_life, _prompt_formula, _boundary]


class ContentGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, now, recent_texts=None):
        gen_cfg = self.config.get("generation", {}) or {}
        provider = (gen_cfg.get("provider") or "template").strip().lower()
        if provider in {"deepseek", "openai"}:
            try:
                return self._generate_with_llm(now, provider, gen_cfg, recent_texts or [])
            except Exception as exc:
                # 模型不可用时退回模板，保证 daemon 不会因为接口故障停摆
                print(f"llm_generate_failed={exc.__class__.__name__}: {exc}")
                print("fallback=template")
        return self._generate_with_template(now)

    def _resolve_api_key(self, gen_cfg, provider):
        env_name = gen_cfg.get("api_key_env") or (
            "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
        )
        key = os.getenv(env_name)
        if key:
            return key

        env_file = gen_cfg.get("api_key_file") or DEFAULT_ENV_FILE
        file_env_name = gen_cfg.get("api_key_file_env") or "AI_NEWS_API_KEY"
        values = _read_env_file(env_file)
        key = values.get(file_env_name) or values.get(env_name)
        if key:
            return key
        raise RuntimeError(f"未找到 API Key（环境变量 {env_name} 或 {env_file} 中的 {file_env_name}）")

    def _build_prompt(self, provider, recent_texts):
        content_cfg = self.config.get("content", {}) or {}
        topic = self.config["topic"]["primary"]
        disclaimer = self.config["topic"]["required_disclaimer"]
        style = content_cfg.get("style", "")
        campaign_url = content_cfg.get("campaign_url", "")
        min_chars = int(content_cfg.get("min_chars", 700))
        max_chars = int(content_cfg.get("max_chars", 1600))
        scenario = random.choice(SCENARIOS)

        recent_titles = []
        for text in recent_texts[:8]:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    recent_titles.append(line[2:].strip())
                    break

        avoid = ""
        if recent_titles:
            avoid = "\n6. 以下标题已经用过，必须换一个完全不同的切入角度和标题，不要复用：\n" + "\n".join(
                f"   - {title}" for title in recent_titles
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
        default_base = "https://api.deepseek.com/v1" if provider == "deepseek" else "https://api.openai.com/v1"
        default_model = "deepseek-chat" if provider == "deepseek" else "gpt-4.1"
        base = (gen_cfg.get("api_base") or default_base).rstrip("/")
        model = gen_cfg.get("model") or default_model

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是中文新媒体编辑，写作克制、具体、有分寸，不写套话。"},
                {"role": "user", "content": self._build_prompt(provider, recent_texts)},
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

    def _generate_with_template(self, now):
        # 用「日期+小时」做种子：同一小时内结果稳定，跨小时自动轮换模板，
        # 保证连续多篇不会撞同一套结构。
        rng = random.Random(now.strftime("%Y%m%d%H"))
        template = TEMPLATES[rng.randrange(len(TEMPLATES))]
        scenario = rng.choice(SCENARIOS)
        campaign_url = self.config.get("content", {}).get("campaign_url", "")
        disclaimer = self.config["topic"]["required_disclaimer"]
        return template(rng, scenario, disclaimer, campaign_url)

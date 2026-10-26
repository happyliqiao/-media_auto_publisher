import re


def _compact(text):
    return re.sub(r"\s+", "", text)


def _bigrams(text):
    compact = _compact(text)
    return {compact[i:i + 2] for i in range(len(compact) - 1)}


def similarity(a, b):
    """字符二元组 Jaccard 相似度，用于识别与近期内容高度重复的稿件。"""
    grams_a, grams_b = _bigrams(a), _bigrams(b)
    if not grams_a or not grams_b:
        return 0.0
    return len(grams_a & grams_b) / len(grams_a | grams_b)


def _extract_title(content):
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


class ContentReviewer:
    def __init__(self, config):
        self.config = config

    def review(self, content: str, recent_texts=None):
        content_cfg = self.config.get("content", {})
        review_cfg = self.config.get("review", {})
        min_chars = int(content_cfg.get("min_chars", 700))
        max_chars = int(content_cfg.get("max_chars", 1600))
        blocked_terms = review_cfg.get("blocked_terms", [])
        required_terms = review_cfg.get("required_terms", [])
        max_similarity = float(review_cfg.get("max_similarity", 0.65))
        block_on_duplicate = bool(review_cfg.get("block_on_duplicate", True))
        disclaimer = self.config.get("topic", {}).get("required_disclaimer", "")

        compact = _compact(content)
        issues = []

        if len(compact) < min_chars:
            issues.append(f"内容过短：{len(compact)} < {min_chars}")
        if len(compact) > max_chars:
            issues.append(f"内容过长：{len(compact)} > {max_chars}")

        for term in blocked_terms:
            if term and term in content:
                issues.append(f"包含高风险词：{term}")

        for term in required_terms:
            if term and term not in content:
                issues.append(f"缺少必备词：{term}")

        if disclaimer and disclaimer not in content:
            issues.append("缺少免责提示")

        title = _extract_title(content)
        if not title:
            issues.append("缺少一级标题")
        elif len(title) > 30:
            issues.append(f"标题过长：{len(title)} > 30")

        top_similarity = 0.0
        for previous in recent_texts or []:
            score = similarity(content, previous)
            top_similarity = max(top_similarity, score)
        if top_similarity >= max_similarity:
            message = f"与近期内容高度重复：相似度 {top_similarity:.2f} >= {max_similarity}"
            if block_on_duplicate:
                issues.append(message)
            else:
                print(f"warning=duplicate score={top_similarity:.2f}")

        return {
            "passed": not issues,
            "issues": issues,
            "char_count": len(compact),
            "title": title,
            "max_similarity": round(top_similarity, 4),
        }

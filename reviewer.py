import re


class ContentReviewer:
    def __init__(self, config):
        self.config = config

    def review(self, content: str):
        content_cfg = self.config.get("content", {})
        review_cfg = self.config.get("review", {})
        min_chars = int(content_cfg.get("min_chars", 700))
        max_chars = int(content_cfg.get("max_chars", 1400))
        blocked_terms = review_cfg.get("blocked_terms", [])
        required_terms = review_cfg.get("required_terms", [])

        compact = re.sub(r"\s+", "", content)
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

        if "免费" in content and "以官方" not in content:
            issues.append("涉及免费额度但缺少官方说明提示")

        title = ""
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if title and len(title) > 30:
            issues.append(f"标题过长：{len(title)} > 30")

        return {
            "passed": not issues,
            "issues": issues,
            "char_count": len(compact),
        }

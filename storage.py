import json
from pathlib import Path


def _extract_title(content):
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


class ContentStorage:
    def __init__(self, config):
        self.storage_dir = Path(config.get("storage_dir", "E:\\AI_Content_AutoPublish"))

    def save(self, content: str, now, review):
        day_dir = self.storage_dir / now.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%d_%H%M%S")
        content_path = day_dir / f"{stamp}.md"
        meta_path = day_dir / f"{stamp}.json"

        content_path.write_text(content, encoding="utf-8")
        meta_path.write_text(
            json.dumps(
                {
                    "created_at": now.isoformat(),
                    "title": _extract_title(content),
                    "review": review,
                    "content_file": str(content_path),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(content_path)

    def recent_texts(self, limit=20):
        """按时间倒序取最近若干篇正文，供查重使用。"""
        if not self.storage_dir.exists():
            return []
        files = sorted(
            self.storage_dir.glob("*/*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        texts = []
        for path in files[:limit]:
            try:
                texts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
        return texts

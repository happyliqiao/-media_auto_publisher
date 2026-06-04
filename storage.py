import json
from pathlib import Path


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
            json.dumps({"review": review, "content_file": str(content_path)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(content_path)

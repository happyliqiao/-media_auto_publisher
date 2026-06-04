from dataclasses import dataclass
import json
from datetime import datetime
from pathlib import Path


@dataclass
class PublishResult:
    platform: str
    status: str
    detail: str


class PublisherManager:
    def __init__(self, config):
        self.config = config
        self.dry_run = bool(config.get("dry_run", True))
        self.platforms = config.get("platforms", {})

    def publish(self, content, saved_path, review):
        results = []
        for name, cfg in self.platforms.items():
            if not cfg.get("enabled", False):
                results.append(PublishResult(name, "disabled", "平台未启用").__dict__)
                continue

            if not review.get("passed"):
                results.append(PublishResult(name, "blocked", "内容审核未通过，已停止发布").__dict__)
                continue

            if self.dry_run:
                queue_path = self._write_publish_queue(name, content, saved_path, "dry_run")
                results.append(PublishResult(name, "dry_run", f"未真实发布，待发布记录：{queue_path}").__dict__)
                continue

            mode = cfg.get("mode", "manual")
            if name == "wechat" and mode == "official_api":
                results.append(self._publish_wechat(content, cfg).__dict__)
            else:
                results.append(PublishResult(name, "manual_required", "未配置官方接口或授权会话，需要人工确认发布").__dict__)
        return results

    def _write_publish_queue(self, platform, content, saved_path, status):
        storage_dir = Path(self.config.get("storage_dir", "E:\\AI_Content_AutoPublish"))
        queue_dir = storage_dir / "_publish_queue" / platform
        queue_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        queue_path = queue_dir / f"{stamp}.json"
        queue_path.write_text(
            json.dumps(
                {
                    "platform": platform,
                    "status": status,
                    "content_file": saved_path,
                    "content_preview": content[:300],
                    "created_at": stamp,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(queue_path)

    def _publish_wechat(self, content, cfg):
        return PublishResult(
            "wechat",
            "not_configured",
            "微信公众号官方 API 需要配置 app_id/app_secret、access_token、草稿素材和群发流程后才能发布",
        )

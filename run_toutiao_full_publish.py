"""今日头条「完整发布」入口（兼容旧命令名）。

实际实现统一在 toutiao_browser.py 中，避免两套 DOM 适配逻辑各自演化。
本文件只做参数转发，便于沿用原来的调用方式。

用法：
    python run_toutiao_full_publish.py            # 填页面不点发布
    python run_toutiao_full_publish.py --submit   # 真实发布
"""

import sys

from toutiao_browser import publish_latest


def main():
    submit = "--submit" in sys.argv
    return publish_latest(dry_run=not submit)


if __name__ == "__main__":
    sys.exit(main())

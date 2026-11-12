"""Import a verified snapshot captured from an opened WeChat article."""

import re
from collections.abc import Iterable
from pathlib import Path

from app.schemas.information import InformationInput


class WeChatSnapshotSource:
    platform = "wechat"

    def __init__(self, snapshot: Path) -> None:
        self.snapshot = snapshot

    def fetch(self) -> Iterable[InformationInput]:
        item = InformationInput.model_validate_json(self.snapshot.read_bytes())
        url = item.source_url
        article_id = re.fullmatch(r"/s/([A-Za-z0-9_-]+)", url.path or "") if url else None
        if (
            not url
            or url.scheme != "https"
            or url.host != "mp.weixin.qq.com"
            or url.port != 443
            or url.username
            or url.password
            or url.query
            or url.fragment
            or not article_id
            or item.source_id != article_id[1]
        ):
            raise ValueError("use a canonical WeChat short link and its article ID")
        if not item.title or not item.source_name:
            raise ValueError("the WeChat snapshot must include the article title and publisher")
        yield item

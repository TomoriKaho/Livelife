"""信源适配接口；平台客户端、调度与自动提取按实际渠道任务接入。"""

from app.services.ingestion.source import InformationSource, collect_information

__all__ = ["InformationSource", "collect_information"]

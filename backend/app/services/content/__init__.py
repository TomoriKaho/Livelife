"""通用信息汇总与提供服务；内部调用，不注册 HTTP 路由。"""

from app.services.content.aggregation import InformationAggregator
from app.services.content.provider import InformationProvider

__all__ = ["InformationAggregator", "InformationProvider"]

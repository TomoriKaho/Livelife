from collections.abc import Iterable
from typing import Protocol

from app.schemas.information import Information, InformationInput
from app.services.content import InformationAggregator


class InformationSource(Protocol):
    """Adapters own access, parsing and checkpoints; no platform client is bundled here."""

    @property
    def platform(self) -> str: ...

    def fetch(self) -> Iterable[InformationInput]: ...


def collect_information(
    source: InformationSource, aggregator: InformationAggregator
) -> tuple[Information, ...]:
    def records() -> Iterable[InformationInput]:
        for item in source.fetch():
            item = InformationInput.model_validate(item)
            if item.platform != source.platform:
                raise ValueError("record platform does not match its source adapter")
            yield item

    return aggregator.ingest(records())

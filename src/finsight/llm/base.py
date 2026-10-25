from typing import Any, Protocol

from finsight.models import ModelSummary


class LLMProvider(Protocol):
    name: str

    def summarize(self, context: dict[str, Any]) -> ModelSummary: ...

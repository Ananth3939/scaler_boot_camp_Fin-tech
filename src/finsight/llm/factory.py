from finsight.config import Settings
from finsight.llm.base import LLMProvider
from finsight.llm.bedrock import BedrockConverseProvider
from finsight.llm.mock import MockLLMProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "bedrock":
        return BedrockConverseProvider(
            region=settings.aws_region,
            model_id=settings.bedrock_model_id,
            profile=settings.aws_profile,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    raise ValueError("LLM_PROVIDER must be either 'mock' or 'bedrock'")

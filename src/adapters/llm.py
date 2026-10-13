from functools import lru_cache
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

@lru_cache(maxsize=1)
def get_chat_model(model: str = 'openai:gpt-4o-mini', temp : float = 0.0, timeout: int = 10):
    # temperature: Model temperature for controlling randomness.
    # max_tokens: Maximum number of output tokens.
    # timeout: Maximum time (in seconds) to wait for a response.
    # max_retries: Maximum number of retry attempts for failed requests.
    # base_url: Custom API endpoint URL.
    # rate_limiter
    return init_chat_model(model=model, temperature=temp, timeout= timeout)
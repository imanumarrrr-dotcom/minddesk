"""OpenAI chat model helpers (via LangChain) and key validation."""
import re

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI


def validate_key(key: str):
    """Return None if the key works, otherwise a human-readable error."""
    try:
        OpenAI(api_key=key, max_retries=0, timeout=20).models.list()
    except AuthenticationError:
        return "OpenAI rejected this key. Check it and try again."
    except APIConnectionError:
        return "Could not reach OpenAI. Check your internet connection and try again."
    except APIStatusError as exc:
        return f"OpenAI rejected the request (status {exc.status_code}). Check your key and account."
    except Exception as exc:  # noqa: BLE001
        return f"Could not validate the key ({type(exc).__name__})."
    return None


def build_llm(api_key: str, model: str, temperature: float = 0.3) -> ChatOpenAI:
    kwargs = dict(model=model.strip(), api_key=api_key, timeout=90, max_retries=2)
    if not re.match(r"^(gpt-5|o\d)", model.strip()):  # reasoning-style models only accept the default temperature
        kwargs["temperature"] = temperature
    return ChatOpenAI(**kwargs)


def token_stream(llm, messages, on_first=None):
    """Yield text chunks; call on_first() when the first token arrives (to remove the 'thinking' dots)."""
    first = True
    for chunk in llm.stream(messages):
        text = chunk.content
        if isinstance(text, list):
            text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        if text:
            if first and on_first:
                on_first()
            first = False
            yield text

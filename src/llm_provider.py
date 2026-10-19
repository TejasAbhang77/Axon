"""Provider configuration shared by Axon's chat and embedding pipelines."""
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_FREE_CHAT_MODEL = "openrouter/free"
OPENROUTER_FREE_EMBEDDING_MODEL = "liquid/lfm-2.5-embedding-350m:free"
OPENAI_CHAT_MODEL = "gpt-4o-mini"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


def get_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
    if provider not in {"openrouter", "openai"}:
        raise ValueError("AI_PROVIDER must be 'openrouter' or 'openai'.")
    return provider


def get_api_key() -> str | None:
    return os.getenv("OPENROUTER_API_KEY" if get_provider() == "openrouter" else "OPENAI_API_KEY")


def has_api_key() -> bool:
    return bool(get_api_key())


def create_client() -> OpenAI:
    provider = get_provider()
    api_key = get_api_key()
    if not api_key:
        variable = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
        raise ValueError(f"{variable} is not set. Add it to the project .env file or hosting secrets.")
    options = {"api_key": api_key}
    if provider == "openrouter":
        options["base_url"] = OPENROUTER_BASE_URL
    return OpenAI(**options)


def get_chat_model() -> str:
    default = OPENROUTER_FREE_CHAT_MODEL if get_provider() == "openrouter" else OPENAI_CHAT_MODEL
    return os.getenv("CHAT_MODEL", default).strip()


def get_embedding_model() -> str:
    default = OPENROUTER_FREE_EMBEDDING_MODEL if get_provider() == "openrouter" else OPENAI_EMBEDDING_MODEL
    return os.getenv("EMBEDDING_MODEL", default).strip()


def is_openrouter_free_embedding() -> bool:
    return get_provider() == "openrouter" and get_embedding_model() == OPENROUTER_FREE_EMBEDDING_MODEL

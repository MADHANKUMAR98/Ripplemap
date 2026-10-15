"""Configuration settings for RippleMap loaded from environment variables."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file from workspace root if present
load_dotenv()


@dataclass(frozen=True)
class Config:
    host: str = os.getenv("FALKORDB_HOST", "localhost")
    port: int = int(os.getenv("FALKORDB_PORT", "6379"))
    graph_name: str = os.getenv("FALKORDB_GRAPH", "ripplemap")
    timeout_ms: int = int(os.getenv("FALKORDB_TIMEOUT_MS", "5000"))
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY", "").strip() or None
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"

    @property
    def is_groq_configured(self) -> bool:
        """Returns True if a non-empty Groq API key is present in environment."""
        return bool(self.groq_api_key)


config = Config()


# -*- coding: utf-8 -*-
"""Environment-backed Knowledge Factory settings."""
from __future__ import annotations

from dataclasses import dataclass
import os


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else int(raw)
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}.")
    return value


def _float(name: str, default: float, minimum: float = 0.1) -> float:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else float(raw)
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}.")
    return value


@dataclass(frozen=True, slots=True)
class KnowledgeFactorySettings:
    enabled: bool
    sql_connection_string: str | None
    api_key: str | None
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    embedding_api_key: str | None
    embedding_base_url: str | None
    ollama_host: str | None
    chunk_max_tokens: int
    chunk_overlap_tokens: int
    index_version: str
    poll_interval_seconds: float
    lease_seconds: int
    max_concurrency: int
    max_reclaim_retries: int
    apply_migrations: bool

    @classmethod
    def from_env(cls) -> "KnowledgeFactorySettings":
        settings = cls(
            enabled=_bool("ASOFT_AI_KF_ENABLED", True),
            sql_connection_string=(os.getenv("ASOFT_ERPX_KM_SQL_CONNECTION_STRING", "").strip() or os.getenv("ASOFT_ERPX_SQL_CONNECTION_STRING", "").strip() or None),
            api_key=os.getenv("ASOFT_ERPX_KM_API_KEY") or os.getenv("ASOFT_SERVICES_API_KEY") or None,
            embedding_provider=os.getenv("ASOFT_AI_KF_EMBEDDING_PROVIDER", "openai_credential").strip(),
            embedding_model=os.getenv("ASOFT_AI_KF_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
            embedding_dimensions=_int("ASOFT_AI_KF_EMBEDDING_DIMENSIONS", 1536),
            embedding_api_key=os.getenv("ASOFT_AI_KF_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
            embedding_base_url=os.getenv("ASOFT_AI_KF_EMBEDDING_BASE_URL") or None,
            ollama_host=os.getenv("ASOFT_AI_KF_OLLAMA_HOST") or None,
            chunk_max_tokens=_int("ASOFT_AI_KF_CHUNK_MAX_TOKENS", 700, 50),
            chunk_overlap_tokens=_int("ASOFT_AI_KF_CHUNK_OVERLAP_TOKENS", 80, 0),
            index_version=os.getenv("ASOFT_AI_KF_INDEX_VERSION", "rag.v2").strip(),
            poll_interval_seconds=_float("ASOFT_AI_KF_POLL_SECONDS", 2.0),
            lease_seconds=_int("ASOFT_AI_KF_LEASE_SECONDS", 120, 15),
            max_concurrency=_int("ASOFT_AI_KF_MAX_CONCURRENCY", 2),
            max_reclaim_retries=_int("ASOFT_AI_KF_MAX_RECLAIMS", 3, 0),
            apply_migrations=_bool("ASOFT_AI_KF_APPLY_MIGRATIONS", True),
        )
        if settings.chunk_overlap_tokens >= settings.chunk_max_tokens:
            raise RuntimeError("Chunk overlap must be smaller than chunk size.")
        if settings.enabled and not settings.sql_connection_string:
            raise RuntimeError("A SQL connection string is required when Knowledge Factory is enabled.")
        return settings

# -*- coding: utf-8 -*-
"""Embedding model construction using existing provider implementations."""
from __future__ import annotations

from Providers.credential import DashScopeCredential, GeminiCredential, OllamaCredential, OpenAICredential
from Providers.modelBSN.embedding import DashScopeEmbeddingModel, GeminiEmbeddingModel, OllamaEmbeddingModel, OpenAIEmbeddingModel

from ._config import KnowledgeFactorySettings


def create_embedding_model(settings: KnowledgeFactorySettings):
    parameters = {"dimensions": settings.embedding_dimensions}
    if settings.embedding_provider == "openai_credential":
        if not settings.embedding_api_key:
            raise RuntimeError("ASOFT_AI_KF_OPENAI_API_KEY API key is required.")
        credential = OpenAICredential(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
        return OpenAIEmbeddingModel(
            credential=credential,
            model=settings.embedding_model,
            parameters=OpenAIEmbeddingModel.Parameters(**parameters),
        )
    if settings.embedding_provider == "dashscope_credential":
        if not settings.embedding_api_key:
            raise RuntimeError("DashScope embedding API key is required.")
        credential = DashScopeCredential(api_key=settings.embedding_api_key)
        return DashScopeEmbeddingModel(
            credential=credential,
            model=settings.embedding_model,
            parameters=DashScopeEmbeddingModel.Parameters(**parameters),
        )
    if settings.embedding_provider == "gemini_credential":
        if not settings.embedding_api_key:
            raise RuntimeError("Gemini embedding API key is required.")
        credential = GeminiCredential(api_key=settings.embedding_api_key)
        return GeminiEmbeddingModel(
            credential=credential,
            model=settings.embedding_model,
            parameters=GeminiEmbeddingModel.Parameters(**parameters),
        )
    if settings.embedding_provider == "ollama_credential":
        credential = OllamaCredential(host=settings.ollama_host)
        return OllamaEmbeddingModel(
            credential=credential,
            model=settings.embedding_model,
            parameters=OllamaEmbeddingModel.Parameters(**parameters),
        )
    raise RuntimeError(f"Unsupported Knowledge Factory embedding provider: {settings.embedding_provider}.")

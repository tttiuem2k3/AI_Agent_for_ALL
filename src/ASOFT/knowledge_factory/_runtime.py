# -*- coding: utf-8 -*-
"""Application composition for the ASOFT Knowledge Factory."""
from __future__ import annotations

from ._config import KnowledgeFactorySettings
from ._embedding import create_embedding_model
from ._errors import KnowledgeFactoryError
from ._models import PublishResponse


class KnowledgeFactoryRuntime:
    def __init__(
        self,
        settings: KnowledgeFactorySettings,
        *,
        repository=None,
        worker=None,
        embedding_model=None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.embedding_model = embedding_model
        self.worker = worker
        self.configuration_error: str | None = None
        if self.repository is None and settings.sql_connection_string:
            from ._repository import KnowledgeFactoryRepository
            self.repository = KnowledgeFactoryRepository(settings.sql_connection_string)
        if self.embedding_model is None and settings.enabled:
            try:
                self.embedding_model = create_embedding_model(settings)
            except RuntimeError as exc:
                self.configuration_error = str(exc)
        if self.worker is None and self.repository is not None and self.embedding_model is not None:
            from ._worker import KnowledgeFactoryWorker
            self.worker = KnowledgeFactoryWorker(settings, self.repository, self.embedding_model)

    @classmethod
    def from_env(cls) -> "KnowledgeFactoryRuntime":
        return cls(KnowledgeFactorySettings.from_env())

    async def __aenter__(self) -> "KnowledgeFactoryRuntime":
        if self.settings.enabled and self.repository is not None:
            if self.settings.apply_migrations:
                await self.repository.apply_migrations(self.settings.embedding_dimensions)
            await self.repository.validate_schema_contract(self.settings.embedding_dimensions)
        if self.worker is not None:
            await self.worker.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.worker is not None:
            await self.worker.stop()

    async def trigger(self, snapshot_apk: str) -> PublishResponse:
        if not self.settings.enabled:
            raise KnowledgeFactoryError("KNOWLEDGE_FACTORY_DISABLED", "Knowledge Factory is disabled.")
        if self.configuration_error is not None:
            raise KnowledgeFactoryError("KNOWLEDGE_FACTORY_NOT_CONFIGURED", self.configuration_error)
        if self.repository is None or self.worker is None:
            raise KnowledgeFactoryError("KNOWLEDGE_FACTORY_NOT_CONFIGURED", "Knowledge Factory is not configured.")
        response = await self.repository.enqueue_publish(snapshot_apk, self.settings.index_version)
        self.worker.wake()
        return response

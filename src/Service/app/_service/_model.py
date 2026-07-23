# -*- coding: utf-8 -*-
"""Model service: builds a ChatModelBase from stored credential + config."""
from fastapi import HTTPException, status

from ..storage import StorageBase, ChatModelConfig
from Providers.credential import CredentialFactory
from Providers.modelLLM.model import (
    ChatModelAdapterRegistry,
    ChatModelBase,
)


async def get_model(
    user_id: str,
    config: ChatModelConfig,
    storage: StorageBase,
) -> ChatModelBase:
    """Get the model instance from the configuration and storage.

    Args:
        user_id (`str`):
            The user id.
        config (`ChatModelConfig`):
            The chat model configuration.
        storage (`StorageBase`):
            The storage instance.

    Returns:
        `ChatModelBase`:
            The model instance.
    """
    credential_record = await storage.get_credential(
        user_id,
        config.credential_id,
    )
    if credential_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential {config.credential_id!r} not found.",
        )

    credential = CredentialFactory.from_dict(credential_record.data)
    try:
        adapter, explicit = ChatModelAdapterRegistry.select(
            config.model_adapter,
            config.type,
            credential.type,
        )
        card = ChatModelAdapterRegistry.validate(
            adapter,
            config.model,
            config.parameters,
            strict_parameters=explicit,
        )
        model_cls = adapter.model_class
        parameters = (
            model_cls.Parameters(**config.parameters)
            if config.parameters
            else None
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    model_kwargs = {
        "credential": credential,
        "model": config.model,
        "parameters": parameters,
        "context_size": config.context_size or card.context_size,
    }
    return model_cls(**model_kwargs)

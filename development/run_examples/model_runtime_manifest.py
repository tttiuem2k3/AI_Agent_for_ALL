# -*- coding: utf-8 -*-
"""Print the Python chat-adapter/model-card manifest for seed review.

The command is intentionally read-only and never loads credentials. Its JSON
output is the source snapshot used to review ONT1007 migration changes.
"""
import json

from Providers.modelLLM.model import ChatModelAdapterRegistry


def build_manifest() -> list[dict]:
    """Return registered adapters and their model-card parameter schemas."""
    result: list[dict] = []
    for adapter in ChatModelAdapterRegistry.list_adapters():
        result.append(
            {
                "adapter_key": adapter.key,
                "credential_types": sorted(adapter.credential_types),
                "models": [
                    {
                        "model": card.name,
                        "parameter_schema": card.parameter_schema,
                    }
                    for card in adapter.model_class.list_models()
                ],
            },
        )
    return sorted(result, key=lambda item: item["adapter_key"])


if __name__ == "__main__":
    print(json.dumps(build_manifest(), ensure_ascii=False, indent=2))

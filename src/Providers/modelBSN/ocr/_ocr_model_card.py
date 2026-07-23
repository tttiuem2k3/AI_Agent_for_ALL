# -*- coding: utf-8 -*-
"""OCR model metadata loaded from provider YAML files."""
import copy
from datetime import datetime
from typing import Literal, Self, Type

import yaml
from pydantic import BaseModel, Field


class OCRModelCard(BaseModel):
    """Description and parameter schema of an OCR model."""

    type: Literal["ocr_model"] = "ocr_model"
    name: str = Field(description="The OCR model name.")
    label: str = Field(description="The label shown to users.")
    status: Literal["active", "deprecated", "sunset"] = "active"
    deprecated_at: datetime | None = None
    input_types: list[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png"],
    )
    output_types: list[str] = Field(
        default_factory=lambda: ["text/plain", "app/json"],
    )
    languages: list[str] = Field(default_factory=list)
    parameter_schema: dict
    parameters_overrides: dict[str, dict]

    @classmethod
    def from_yaml(
        cls,
        yaml_path: str,
        parameter_class: Type[BaseModel],
    ) -> Self:
        """Load a model card and merge provider parameter overrides."""
        with open(yaml_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)

        base_schema = parameter_class.model_json_schema()
        properties = copy.deepcopy(base_schema.get("properties", {}))
        overrides = config.get("parameter_overrides", {})
        for name, override in overrides.items():
            if override is None or (
                isinstance(override, dict) and override.get("hidden")
            ):
                properties.pop(name, None)
            elif isinstance(override, dict) and name in properties:
                properties[name] = {**properties[name], **override}

        required = [
            name
            for name in base_schema.get("required", [])
            if name in properties
        ]
        return cls(
            name=config["name"],
            label=config["label"],
            status=config.get("status", "active"),
            deprecated_at=config.get("deprecated_at"),
            input_types=config.get(
                "input_types",
                ["image/jpeg", "image/png"],
            ),
            output_types=config.get(
                "output_types",
                ["text/plain", "app/json"],
            ),
            languages=config.get("languages", []),
            parameter_schema={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            parameters_overrides=overrides,
        )

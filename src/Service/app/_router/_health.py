# -*- coding: utf-8 -*-
"""Additive health endpoint for service/runtime probes."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health probe response."""

    status: Literal["ok"] = Field(description="Service health status.")


health_router = APIRouter(tags=["health"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health probe",
)
async def health() -> HealthResponse:
    """Return a lightweight process health marker."""
    return HealthResponse(status="ok")

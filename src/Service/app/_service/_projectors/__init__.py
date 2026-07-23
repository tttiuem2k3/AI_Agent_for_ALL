# -*- coding: utf-8 -*-
"""Built-in event projectors.

Each projector mirrors one cross-session UI feed onto the owning
session via the shared
:class:`~Service.app._service._session_projection.SessionProjection`
primitive. See :class:`~Service.app._types.EventProjector`.
"""
from ._subagent_hitl import SubagentHitlProjector

__all__ = [
    "SubagentHitlProjector",
]

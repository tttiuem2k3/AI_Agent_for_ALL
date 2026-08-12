# -*- coding: utf-8 -*-
"""Workspace router — manage MCP clients and skills on a workspace."""
import base64
import hashlib
import hmac
import mimetypes
import os
import time
from urllib.parse import quote
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..deps import (
    get_current_user_id,
    get_storage,
    get_workspace_manager,
)
from ..workspace_manager import WorkspaceManagerBase
from ..storage import StorageBase
from Capabilities.mcp import MCPClient
from Capabilities.skill import Skill
from Capabilities.workspace import WorkspaceBase

workspace_router = APIRouter(prefix="/workspace", tags=["workspace"])


class AddSkillRequest(BaseModel):
    """The request to add skill."""

    skill_path: str


class ToolInfo(BaseModel):
    """The tool info."""

    name: str
    description: str | None = None


class MCPClientStatus(MCPClient):
    """MCPClient enriched with live tool list and health status."""

    is_healthy: bool = False
    tools: list[ToolInfo] = Field(default_factory=list)

class DirectoryEntry(BaseModel):
    """One entry in a workspace directory listing."""

    name: str
    is_dir: bool
    size_bytes: int | None = None
    updated_at: float | None = None


class DirectoryListing(BaseModel):
    """One directory level plus the resolved path."""

    path: str
    entries: list[DirectoryEntry]


class DownloadTokenResponse(BaseModel):
    """A short-lived token authorizing one file download."""

    token: str
    expires_at: float


_DOWNLOAD_TOKEN_TTL_SECS = 60
_DEFAULT_DOWNLOAD_SECRET = secrets.token_urlsafe(32)


def _download_secret() -> str:
    return os.environ.get("ASOFT_AI_DOWNLOAD_SECRET", _DEFAULT_DOWNLOAD_SECRET)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _download_signature(expires_at: int, user_id: str, path: str) -> bytes:
    payload = f"{expires_at}\0{user_id}\0{path}".encode("utf-8")
    return hmac.new(
        _download_secret().encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()


def _sign_download_token(user_id: str, path: str) -> tuple[str, int]:
    expires_at = int(time.time()) + _DOWNLOAD_TOKEN_TTL_SECS
    signature = _download_signature(expires_at, user_id, path)
    return (
        f"{expires_at}.{_b64(user_id.encode('utf-8'))}.{_b64(signature)}",
        expires_at,
    )


def _verify_download_token(token: str, path: str) -> str:
    try:
        raw_expiry, raw_user, raw_signature = token.split(".")
        expires_at = int(raw_expiry)
        user_id = _unb64(raw_user).decode("utf-8")
        signature = _unb64(raw_signature)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed download token.") from exc
    if expires_at < time.time():
        raise ValueError("Expired download token.")
    expected = _download_signature(expires_at, user_id, path)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid download token.")
    return user_id


async def _resolve_workspace(
    user_id: str,
    agent_id: str,
    session_id: str,
    storage: StorageBase,
    workspace_manager: WorkspaceManagerBase,
) -> WorkspaceBase:
    """Resolve the workspace for the given session, raising 404 if not
    found."""
    session_record = await storage.get_session(user_id, agent_id, session_id)
    if session_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id!r} not found.",
        )
    return await workspace_manager.get_workspace(
        user_id,
        agent_id,
        session_id,
        session_record.config.workspace_id,
    )


# ---------------------------------------------------------------------------
# File browsing endpoints
# ---------------------------------------------------------------------------


@workspace_router.get("/files/dir")
@workspace_router.get("/directories")
async def list_workspace_directory(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    path: str = Query(default=""),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> DirectoryListing:
    """List one directory level from a session's workspace backend."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    backend = workspace.get_backend()
    target = backend.abspath(path, cwd=workspace.workdir)
    entry = await backend.stat(target)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found.",
        )
    if not entry.is_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested path is a file, not a directory.",
        )
    return DirectoryListing(
        path=target,
        entries=[
            DirectoryEntry(
                name=item.name,
                is_dir=item.is_dir,
                size_bytes=item.size_bytes,
                updated_at=item.mtime,
            )
            for item in await backend.scandir(target)
        ],
    )


@workspace_router.post("/files/token")
@workspace_router.post("/files/download-token")
async def create_download_token(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    path: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> DownloadTokenResponse:
    """Mint a short-lived token for browser-native file downloads."""
    await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    token, expires_at = _sign_download_token(user_id, path)
    return DownloadTokenResponse(token=token, expires_at=expires_at)


@workspace_router.get("/files")
async def read_workspace_file(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    path: str = Query(...),
    download: bool = Query(default=False),
    token: str | None = Query(default=None),
    x_user_id: str | None = Header(default=None),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> StreamingResponse:
    """Stream one file from a session's workspace backend."""
    if token is not None:
        try:
            user_id = _verify_download_token(token, path)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
    elif x_user_id:
        user_id = x_user_id
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID header or download token is required.",
        )

    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    backend = workspace.get_backend()
    target = backend.abspath(path, cwd=workspace.workdir)
    basename = backend.basename(target) or "download"
    entry = await backend.stat(target)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )
    if entry.is_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested path is a directory, not a file.",
        )

    headers: dict[str, str] = {}
    if entry.size_bytes is not None:
        headers["Content-Length"] = str(entry.size_bytes)
    if download:
        headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quote(basename)}"
        )
    return StreamingResponse(
        backend.read_stream(target),
        media_type=mimetypes.guess_type(basename)[0]
        or "application/octet-stream",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# MCP endpoints
# ---------------------------------------------------------------------------


@workspace_router.get("/mcp")
async def list_mcps(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> list[MCPClientStatus]:
    """Return all MCP clients with live tool list and health status."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    clients = await workspace.list_mcps()

    results = []
    for client in clients:
        base = client.model_dump()
        try:
            mcp_tools = await client.list_tools()
            tools = [
                ToolInfo(name=t.name, description=t.description)
                for t in mcp_tools
            ]
            results.append(
                MCPClientStatus(
                    **base,
                    is_healthy=True,
                    tools=tools,
                ),
            )
        except Exception:
            results.append(
                MCPClientStatus(
                    **base,
                    is_healthy=False,
                ),
            )

    return results


@workspace_router.post("/mcp", status_code=status.HTTP_201_CREATED)
async def add_mcp(
    mcp: MCPClient,
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> None:
    """Add an MCP client to the session's workspace."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    await workspace.add_mcp(mcp)


@workspace_router.delete(
    "/mcp/{mcp_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_mcp(
    mcp_name: str,
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> None:
    """Remove an MCP client from the session's workspace by name."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    await workspace.remove_mcp(mcp_name)


# ---------------------------------------------------------------------------
# Skill endpoints
# ---------------------------------------------------------------------------


@workspace_router.get("/skill")
async def list_skills(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> list[Skill]:
    """Return all skills available in the session's workspace."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    return await workspace.list_skills()


@workspace_router.post("/skill", status_code=status.HTTP_201_CREATED)
async def add_skill(
    body: AddSkillRequest,
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> None:
    """Add a skill to the session's workspace from the given path."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    await workspace.add_skill(body.skill_path)


@workspace_router.delete(
    "/skill/{skill_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_skill(
    skill_name: str,
    agent_id: str = Query(...),
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> None:
    """Remove a skill from the session's workspace by name."""
    workspace = await _resolve_workspace(
        user_id,
        agent_id,
        session_id,
        storage,
        workspace_manager,
    )
    await workspace.remove_skill(skill_name)

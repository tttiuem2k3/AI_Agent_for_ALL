# -*- coding: utf-8 -*-
"""SQL connection helpers for ASOFT-owned ERPX workers."""
from __future__ import annotations


def normalize_odbc_connection_string(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("A SQL connection string is required.")
    lowered = raw.lower()
    if "driver=" in lowered:
        return raw
    parts: dict[str, str] = {}
    for segment in raw.split(";"):
        if "=" not in segment:
            continue
        key, item = segment.split("=", 1)
        parts[key.strip().lower()] = item.strip()
    server = parts.get("server") or parts.get("data source")
    database = parts.get("database") or parts.get("initial catalog")
    user = parts.get("user id") or parts.get("uid")
    password = parts.get("password") or parts.get("pwd")
    if not server or not database:
        raise ValueError("SQL Server and Database are required.")
    segments = [
        "DRIVER={ODBC Driver 17 for SQL Server}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]
    if user and password:
        segments.extend((f"UID={user}", f"PWD={password}"))
    else:
        segments.append("Trusted_Connection=Yes")
    segments.extend(("Encrypt=No", "TrustServerCertificate=Yes"))
    return ";".join(segments) + ";"

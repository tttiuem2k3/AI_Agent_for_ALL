# -*- coding: utf-8 -*-
"""Resolve the canonical SERVICES address from ERPX environment data."""
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit


_SERVICES_ENVIRONMENT_SQL = """
SELECT KeyName, KeyValue
FROM dbo.ST2101 WITH (NOLOCK)
WHERE KeyName IN ('MainAPIURL', 'MainAPIPort');
"""

_ODBC_DRIVER_PREFERENCE = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _odbc_boolean(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return "yes"
    if normalized in {"false", "no", "0"}:
        return "no"
    raise RuntimeError("The ERPX SQL connection string has an invalid flag.")


def _as_pyodbc_connection_string(
    connection_string: str,
    drivers: list[str],
) -> str:
    """Convert the ERPX ADO.NET SQL string into a pyodbc connection string."""
    fields: dict[str, str] = {}
    for segment in connection_string.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        key, separator, value = segment.partition("=")
        if not separator or not key.strip() or not value.strip():
            raise RuntimeError("The ERPX SQL connection string is invalid.")
        fields[key.strip().lower()] = value.strip()

    if "driver" in fields:
        return connection_string

    driver = next(
        (
            preferred
            for preferred in _ODBC_DRIVER_PREFERENCE
            if preferred in drivers
        ),
        None,
    )
    if driver is None:
        driver = next(
            (item for item in drivers if "sql server" in item.lower()),
            None,
        )
    if driver is None:
        raise RuntimeError("A Microsoft SQL Server ODBC driver is required.")

    def value_for(*keys: str) -> str | None:
        return next((fields[key] for key in keys if key in fields), None)

    server = value_for("server", "data source", "address", "addr")
    database = value_for("database", "initial catalog")
    if not server or not database:
        raise RuntimeError(
            "The ERPX SQL connection string requires Server and Database.",
        )

    odbc_fields = [
        ("DRIVER", driver),
        ("SERVER", server),
        ("DATABASE", database),
    ]
    trusted = value_for("trusted_connection", "integrated security")
    trusted_enabled = trusted is not None and trusted.lower() in {
        "true",
        "yes",
        "sspi",
        "1",
    }
    if trusted_enabled:
        odbc_fields.append(("Trusted_Connection", "yes"))
    else:
        user_id = value_for("user id", "uid")
        password = value_for("password", "pwd")
        if not user_id or password is None:
            raise RuntimeError(
                "The ERPX SQL connection string requires SQL credentials.",
            )
        odbc_fields.extend((("UID", user_id), ("PWD", password)))

    trust_certificate = value_for("trustservercertificate")
    if trust_certificate is not None:
        odbc_fields.append(
            ("TrustServerCertificate", _odbc_boolean(trust_certificate)),
        )
    encrypt = value_for("encrypt")
    if encrypt is not None:
        odbc_fields.append(("Encrypt", _odbc_boolean(encrypt)))

    return ";".join(
        f"{key}={_odbc_value(value)}"
        for key, value in odbc_fields
    ) + ";"


def _single_value(rows: list[Any], key: str) -> str | None:
    values = {
        str(row[1]).strip()
        for row in rows
        if str(row[0]).strip() == key and row[1] is not None
        and str(row[1]).strip()
    }
    if len(values) > 1:
        raise RuntimeError(
            f"ST2101 contains conflicting values for {key}.",
        )
    return next(iter(values), None)


def build_services_base_url(domain: str, port: str | None) -> str:
    """Build the same SERVICES origin represented by MainAPIURL/MainAPIPort."""
    raw_domain = domain.strip().rstrip("/")
    if not raw_domain:
        raise RuntimeError("ST2101.MainAPIURL is required.")
    candidate = (
        raw_domain
        if raw_domain.lower().startswith(("http://", "https://"))
        else f"http://{raw_domain}"
    )
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RuntimeError("ST2101.MainAPIURL is not a valid SERVICES origin.")

    configured_port = port.strip() if port else ""
    if configured_port:
        try:
            port_number = int(configured_port)
        except ValueError as exc:
            raise RuntimeError("ST2101.MainAPIPort must be an integer.") from exc
        if port_number < 1 or port_number > 65535:
            raise RuntimeError("ST2101.MainAPIPort is outside the valid range.")
        if parsed.port is not None and parsed.port != port_number:
            raise RuntimeError(
                "ST2101 MainAPIURL/MainAPIPort contain conflicting ports.",
            )
    else:
        port_number = parsed.port

    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    port_suffix = f":{port_number}" if port_number is not None else ""
    return f"{parsed.scheme}://{host}{port_suffix}"


def resolve_services_base_url(
    connection_string: str,
    *,
    connect: Callable[..., Any] | None = None,
) -> str:
    """Read only the two canonical SERVICES environment rows from ERPX SQL."""
    if not connection_string:
        raise RuntimeError("ASOFT_ERPX_SQL_CONNECTION_STRING is required.")
    if connect is None:
        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError(
                "pyodbc is required to resolve the SERVICES address.",
            ) from exc
        connection_string = _as_pyodbc_connection_string(
            connection_string,
            list(pyodbc.drivers()),
        )
        connect = pyodbc.connect

    try:
        with connect(connection_string, timeout=10) as connection:
            cursor = connection.cursor()
            cursor.execute(_SERVICES_ENVIRONMENT_SQL)
            rows = list(cursor.fetchall())
    except Exception as exc:
        raise RuntimeError(
            "Unable to read the SERVICES address from ERPX SQL.",
        ) from exc

    domain = _single_value(rows, "MainAPIURL")
    if domain is None:
        raise RuntimeError("ST2101.MainAPIURL is required.")
    return build_services_base_url(
        domain,
        _single_value(rows, "MainAPIPort"),
    )

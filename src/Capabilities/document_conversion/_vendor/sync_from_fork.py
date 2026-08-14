# -*- coding: utf-8 -*-
"""Sync the private native converter from the ASOFT-maintained fork."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPABILITY = HERE.parent
NATIVE = CAPABILITY / "_native"
BINDING = NATIVE / "binding"
DEFAULT_SOURCE = Path(r"E:\Asoft\anydoc")


def _git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source), *args], text=True
    ).strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _copy_runtime_source(source: Path) -> None:
    if NATIVE.exists():
        shutil.rmtree(NATIVE)
    NATIVE.mkdir(parents=True)

    for item in (source / "src").iterdir():
        destination = NATIVE / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    shutil.copy2(source / "Cargo.toml", NATIVE / "Cargo.toml")
    shutil.copy2(source / "Cargo.lock", NATIVE / "Cargo.lock")
    shutil.copy2(source / "rustfmt.toml", NATIVE / "rustfmt.toml")

    python_source = source / "python"
    BINDING.mkdir(parents=True)
    shutil.copy2(python_source / "src" / "lib.rs", BINDING / "lib.rs")
    shutil.copy2(python_source / "src" / "document.rs", BINDING / "document.rs")
    shutil.copy2(python_source / "Cargo.toml", BINDING / "Cargo.toml")
    shutil.copy2(python_source / "pyproject.toml", BINDING / "pyproject.toml")
    shutil.copytree(
        python_source / "anydoc",
        BINDING / "asoft_document_conversion_native",
    )

    old_stub = BINDING / "asoft_document_conversion_native" / "_anydoc.pyi"
    if old_stub.exists():
        old_stub.rename(old_stub.with_name("_native.pyi"))


def _rewrite_core_manifest() -> None:
    path = NATIVE / "Cargo.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('members = ["node", "python", "wasm"]', 'members = ["binding"]')
    text = text.replace('exclude = ["fuzz"]\n', '')
    text = text.replace('name = "anydoc"', 'name = "asoft_document_conversion_engine"', 1)
    lines = [
        line for line in text.splitlines()
        if not line.startswith(("repository = ", "readme = ", "include = "))
    ]
    text = "\n".join(lines) + "\n"
    text = text.replace(
        "[dev-dependencies]",
        '[lib]\npath = "lib.rs"\n\n[dev-dependencies]',
    )
    _write(path, text)


def _rewrite_core_source() -> None:
    for path in NATIVE.rglob("*.rs"):
        if BINDING in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "anydoc converts documents to GitHub-Flavored Markdown.",
            "ASOFT document conversion engine converts documents to GitHub-Flavored Markdown.",
        )
        text = text.replace(
            "https://github.com/firecrawl/pdf-inspector",
            "https://crates.io/crates/pdf-inspector",
        )
        _write(path, text)


def _rewrite_binding_manifest() -> None:
    path = BINDING / "Cargo.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('name = "anydoc-python"', 'name = "asoft-document-conversion-native"')
    text = text.replace(
        'description = "Python bindings for anydoc"',
        'description = "Python bindings for ASOFT document conversion engine"',
    )
    text = text.replace(
        'anydoc = { path = ".." }',
        'asoft_document_conversion_engine = { path = ".." }',
    )
    text = "\n".join(
        line for line in text.splitlines() if not line.startswith("repository = ")
    ) + "\n"
    text = text.replace(
        '[lib]\ncrate-type = ["cdylib"]',
        '[lib]\npath = "lib.rs"\ncrate-type = ["cdylib"]',
    )
    _write(path, text)


def _rewrite_pyproject() -> None:
    path = BINDING / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('name = "firecrawl-anydoc"', 'name = "asoft-document-conversion-native"')
    text = text.replace(
        'module-name = "anydoc._anydoc"',
        'module-name = "asoft_document_conversion_native._native"',
    )
    lines: list[str] = []
    skip_urls = False
    for line in text.splitlines():
        if line.startswith("# The distribution installs as") or "PyPI is held" in line:
            continue
        if line.startswith("readme = "):
            continue
        if line == "[project.urls]":
            skip_urls = True
            continue
        if skip_urls and line.startswith("["):
            skip_urls = False
        if not skip_urls:
            lines.append(line)
    _write(path, "\n".join(lines).rstrip() + "\n")


def _rewrite_binding_source() -> None:
    for path in (BINDING / "lib.rs", BINDING / "document.rs"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("anydoc::", "asoft_document_conversion_engine::")
        text = text.replace('module = "anydoc"', 'module = "asoft_document_conversion_native"')
        text = text.replace("    anydoc,\n", "    asoft_document_conversion_native,\n")
        text = text.replace("fn _anydoc(", "fn _native(")
        text = text.replace("bindings for anydoc", "bindings for ASOFT document conversion engine")
        text = text.replace("which anydoc does not do", "which this engine does not do")
        _write(path, text)

    package = BINDING / "asoft_document_conversion_native"
    for path in package.rglob("*.py*"):
        if path.suffix not in {".py", ".pyi"}:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "from anydoc._anydoc import",
            "from asoft_document_conversion_native._native import",
        )
        text = text.replace("anydoc._anydoc", "asoft_document_conversion_native._native")
        text = text.replace("`tests/test_anydoc.py`", "`native binding tests`")
        text = text.replace("which anydoc does not do", "which this engine does not do")
        _write(path, text)


def _rewrite_lockfile() -> None:
    path = NATIVE / "Cargo.lock"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'name = "anydoc"': 'name = "asoft_document_conversion_engine"',
        'name = "anydoc-python"': 'name = "asoft-document-conversion-native"',
        'name = "anydoc-node"': 'name = "upstream-node-binding-unused"',
        'name = "anydoc-wasm"': 'name = "upstream-wasm-binding-unused"',
        ' "anydoc",': ' "asoft_document_conversion_engine",',
        '["anydoc",': '["asoft_document_conversion_engine",',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    _write(path, text)


def _normalize_lockfile() -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        candidate = Path.home() / ".cargo" / "bin" / "cargo.exe"
        if candidate.exists():
            cargo = str(candidate)
    if cargo is None:
        raise SystemExit("Rust cargo is required to normalize the flattened native Cargo.lock.")

    commands = [
        [cargo, "metadata", "--offline", "--format-version", "1"],
        [cargo, "metadata", "--format-version", "1"],
    ]
    last_error = ""
    for command in commands:
        result = subprocess.run(
            command, cwd=NATIVE, text=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, check=False,
        )
        if result.returncode == 0:
            return
        last_error = result.stderr.strip()
    raise SystemExit(f"Unable to normalize native Cargo.lock: {last_error}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_metadata(source: Path) -> None:
    metadata = {
        "sourceRepository": "https://github.com/tttiuem2k3/anydoc",
        "upstreamRepository": "https://github.com/firecrawl/anydoc",
        "sourceCommit": _git(source, "rev-parse", "HEAD"),
        "sourceVersion": _git(source, "describe", "--tags", "--always"),
        "integration": "Capabilities.document_conversion",
        "semanticPatches": [],
    }
    _write(HERE / "upstream.json", json.dumps(metadata, indent=2) + "\n")
    shutil.copy2(source / "LICENSE", HERE / "UPSTREAM_LICENSE_MIT")
    shutil.copy2(source / "Cargo.lock", HERE / "UPSTREAM_CARGO_LOCK")

    rows: list[str] = []
    for path in sorted(NATIVE.rglob("*")):
        if path.is_file():
            rows.append(f"{_sha256(path)}  {path.relative_to(NATIVE).as_posix()}")
    _write(HERE / "engine_manifest.sha256", "\n".join(rows) + "\n")


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not (source / "Cargo.toml").exists():
        raise SystemExit(f"Invalid source repository: {source}")
    if _git(source, "status", "--porcelain"):
        raise SystemExit("Source fork has local changes; sync requires a clean working tree.")

    _copy_runtime_source(source)
    _rewrite_core_manifest()
    _rewrite_core_source()
    _rewrite_binding_manifest()
    _rewrite_pyproject()
    _rewrite_binding_source()
    _rewrite_lockfile()
    _normalize_lockfile()
    _write_metadata(source)
    print(f"Synced document conversion runtime from {_git(source, 'rev-parse', 'HEAD')}")


if __name__ == "__main__":
    main()

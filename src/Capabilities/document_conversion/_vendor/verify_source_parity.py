# -*- coding: utf-8 -*-
"""Verify the flattened native source differs only by approved rebranding."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "_native"
BINDING = NATIVE / "binding"
DEFAULT_SOURCE = Path(r"E:\Asoft\anydoc")


def _core_expected(text: str) -> str:
    text = text.replace(
        "anydoc converts documents to GitHub-Flavored Markdown.",
        "ASOFT document conversion engine converts documents to GitHub-Flavored Markdown.",
    )
    return text.replace(
        "https://github.com/firecrawl/pdf-inspector",
        "https://crates.io/crates/pdf-inspector",
    )


def _binding_expected(text: str) -> str:
    text = text.replace("anydoc::", "asoft_document_conversion_engine::")
    text = text.replace('module = "anydoc"', 'module = "asoft_document_conversion_native"')
    text = text.replace("    anydoc,\n", "    asoft_document_conversion_native,\n")
    text = text.replace("fn _anydoc(", "fn _native(")
    text = text.replace("bindings for anydoc", "bindings for ASOFT document conversion engine")
    return text.replace("which anydoc does not do", "which this engine does not do")


def _python_expected(text: str) -> str:
    text = text.replace(
        "from anydoc._anydoc import",
        "from asoft_document_conversion_native._native import",
    )
    text = text.replace("anydoc._anydoc", "asoft_document_conversion_native._native")
    text = text.replace("`tests/test_anydoc.py`", "`native binding tests`")
    return text.replace("which anydoc does not do", "which this engine does not do")


def _assert_core(source_root: Path) -> int:
    count = 0
    for source in source_root.rglob("*.rs"):
        relative = source.relative_to(source_root)
        target = NATIVE / relative
        if not target.exists():
            raise AssertionError(f"Missing native core file: {relative}")
        if target.read_text(encoding="utf-8") != _core_expected(source.read_text(encoding="utf-8")):
            raise AssertionError(f"Unexpected core drift: {relative}")
        count += 1
    return count


def _assert_binding(source_root: Path) -> int:
    count = 0
    for name in ("lib.rs", "document.rs"):
        source = source_root / name
        target = BINDING / name
        if target.read_text(encoding="utf-8") != _binding_expected(source.read_text(encoding="utf-8")):
            raise AssertionError(f"Unexpected binding drift: {name}")
        count += 1
    return count


def _assert_python_package(source_root: Path) -> int:
    target_root = BINDING / "asoft_document_conversion_native"
    count = 0
    for source in source_root.iterdir():
        if not source.is_file():
            continue
        target_name = "_native.pyi" if source.name == "_anydoc.pyi" else source.name
        target = target_root / target_name
        if not target.exists():
            raise AssertionError(f"Missing binding package file: {target_name}")
        if source.suffix in {".py", ".pyi"}:
            expected = _python_expected(source.read_text(encoding="utf-8"))
            if target.read_text(encoding="utf-8") != expected:
                raise AssertionError(f"Unexpected Python binding drift: {target_name}")
        count += 1
    return count


def _source_inventory(source: Path) -> set[str]:
    files = {p.relative_to(source / "src").as_posix() for p in (source / "src").rglob("*") if p.is_file()}
    files.update({"Cargo.toml", "Cargo.lock", "rustfmt.toml", "binding/lib.rs", "binding/document.rs", "binding/Cargo.toml", "binding/pyproject.toml"})
    for item in (source / "python" / "anydoc").iterdir():
        if item.is_file():
            name = "_native.pyi" if item.name == "_anydoc.pyi" else item.name
            files.add(f"binding/asoft_document_conversion_native/{name}")
    return files


def _is_generated(path: Path) -> bool:
    relative = path.relative_to(NATIVE)
    return (
        bool({"target", "dist", "__pycache__"}.intersection(relative.parts))
        or path.suffix in {".pyc", ".pyo"}
    )


def _assert_inventory(source: Path) -> int:
    expected = _source_inventory(source)
    actual = {
        p.relative_to(NATIVE).as_posix()
        for p in NATIVE.rglob("*")
        if p.is_file() and not _is_generated(p)
    }
    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise AssertionError(f"Native inventory drift: missing={missing[:5]} extra={extra[:5]}")
    return len(actual)


def _assert_layout() -> None:
    capability = HERE.parent
    nested = [p for p in capability.rglob("src") if p.is_dir()]
    if nested:
        raise AssertionError(f"Nested src directories are not allowed: {nested}")
    for stale in (capability / "_native_engine", capability / "_native_adapter.py"):
        if stale.exists():
            raise AssertionError(f"Stale document conversion layout remains: {stale}")


def _assert_branding() -> None:
    for path in NATIVE.rglob("*"):
        if not path.is_file() or _is_generated(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "anydoc" in text or "firecrawl" in text:
            raise AssertionError(f"Upstream branding leaked into native runtime: {path}")


def _assert_manifests() -> None:
    core = tomllib.loads((NATIVE / "Cargo.toml").read_text(encoding="utf-8"))
    binding = tomllib.loads((BINDING / "Cargo.toml").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((BINDING / "pyproject.toml").read_text(encoding="utf-8"))
    assert core["workspace"]["members"] == ["binding"]
    assert core["package"]["name"] == "asoft_document_conversion_engine"
    assert core["lib"]["path"] == "lib.rs"
    assert binding["package"]["name"] == "asoft-document-conversion-native"
    assert binding["lib"]["path"] == "lib.rs"
    assert "asoft_document_conversion_engine" in binding["dependencies"]
    assert pyproject["project"]["name"] == "asoft-document-conversion-native"
    assert pyproject["tool"]["maturin"]["module-name"] == "asoft_document_conversion_native._native"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _assert_engine_manifest() -> None:
    rows = {}
    for line in (HERE / "engine_manifest.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        rows[relative] = digest
    files = {
        p.relative_to(NATIVE).as_posix(): p
        for p in NATIVE.rglob("*")
        if p.is_file() and not _is_generated(p)
    }
    if set(rows) != set(files):
        raise AssertionError("Engine manifest inventory does not match native source inventory")
    bad = [name for name, path in files.items() if _sha256(path) != rows[name]]
    if bad:
        raise AssertionError(f"Engine manifest hash mismatch: {bad[:5]}")


def _assert_metadata(source: Path) -> None:
    metadata = json.loads((HERE / "upstream.json").read_text(encoding="utf-8"))
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if metadata.get("sourceCommit") != head:
        raise AssertionError(f"Pinned source commit differs from source HEAD: {metadata.get('sourceCommit')} != {head}")


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    core_count = _assert_core(source / "src")
    binding_count = _assert_binding(source / "python" / "src")
    package_count = _assert_python_package(source / "python" / "anydoc")
    inventory_count = _assert_inventory(source)
    _assert_layout()
    _assert_branding()
    _assert_manifests()
    _assert_engine_manifest()
    _assert_metadata(source)
    print(
        f"source_parity_ok core={core_count} binding={binding_count} "
        f"python_package={package_count} inventory={inventory_count} "
        "layout=ok branding=ok manifests=ok hashes=ok metadata=ok"
    )


if __name__ == "__main__":
    main()

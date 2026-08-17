# -*- coding: utf-8 -*-
"""Human-readable append-only process log for Knowledge Factory runs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any

_RUN_PATTERN = re.compile(r"(?m)^#(\d+)\b")


class KnowledgeFactoryProcessLogger:
    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path(__file__).with_name("log.txt")
        self._lock = threading.Lock()

    def start_run(self, *, job_apk: str, snapshot_apk: str) -> int:
        with self._lock:
            run_id = self._next_run_id()
            self._append(
                "\n".join(
                    [
                        f"#{run_id}",
                        f"Thời gian: {self._now()}",
                        f"JobAPK: {job_apk}",
                        f"SnapshotAPK: {snapshot_apk}",
                        "Trạng thái: Bắt đầu xử lý",
                        "",
                    ]
                )
            )
            return run_id

    def step(
        self,
        run_id: int,
        title: str,
        *,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            lines = [f"#{run_id} - Bước: {title}"]
            if input_data is not None:
                lines.append(f"Đầu vào: {self._format(input_data)}")
            if output_data is not None:
                lines.append(f"Đầu ra: {self._format(output_data)}")
            lines.append("")
            self._append("\n".join(lines))

    def finish(self, run_id: int, *, status: str, output_data: dict[str, Any] | None = None) -> None:
        self.step(run_id, "Kết thúc", output_data={"status": status, **(output_data or {})})

    def _next_run_id(self) -> int:
        if not self.log_path.exists():
            return 1
        content = self.log_path.read_text(encoding="utf-8", errors="ignore")
        matches = [int(value) for value in _RUN_PATTERN.findall(content)]
        return (max(matches) + 1) if matches else 1

    def _append(self, text: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(text.rstrip() + "\n")

    @staticmethod
    def _format(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

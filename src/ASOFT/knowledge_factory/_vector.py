# -*- coding: utf-8 -*-
"""SQL Server vector conversion helpers."""
from __future__ import annotations
import math


class SQLServerVectorCodec:
    @staticmethod
    def to_sql_literal(vector: list[float], *, dimensions: int) -> str:
        if len(vector) != dimensions:
            raise ValueError(f"Embedding dimension mismatch: expected {dimensions}, got {len(vector)}.")
        values = []
        for raw in vector:
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError("Embedding vector contains a non-finite value.")
            values.append(repr(value))
        return "[" + ",".join(values) + "]"

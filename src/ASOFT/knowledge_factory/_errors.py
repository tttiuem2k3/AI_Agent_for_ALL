# -*- coding: utf-8 -*-
"""Safe, persistable Knowledge Factory errors."""


class KnowledgeFactoryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


class LeaseLostError(KnowledgeFactoryError):
    def __init__(self) -> None:
        super().__init__("LEASE_LOST", "The indexing worker no longer owns the job lease.")

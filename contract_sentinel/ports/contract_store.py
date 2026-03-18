from __future__ import annotations

from abc import ABC, abstractmethod


class ContractStore(ABC):
    """Port for reading and writing versioned contract documents.

    All keys are relative — the adapter is responsible for any path prefixing.
    `list_files` returns keys ordered by recency (newest first) so callers can
    take the first element to resolve the latest contract without version parsing.
    """

    @abstractmethod
    def get_file(self, key: str) -> str:
        """Return the string content stored at *key*."""
        ...

    @abstractmethod
    def put_file(self, key: str, content: str) -> None:
        """Write *content* (UTF-8 string) to *key*, overwriting any existing value."""
        ...

    @abstractmethod
    def list_files(self, prefix: str) -> list[str]:
        """Return all keys that share *prefix*, ordered by last-modified descending."""
        ...

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Return True if an object exists at *key*, False otherwise."""
        ...

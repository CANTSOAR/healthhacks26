from __future__ import annotations

from typing import Any, Protocol


class TableNotFound(KeyError):
    pass


class DataService(Protocol):
    name: str

    def list_tables(self) -> list[str]: ...

    def get_table(self, name: str, **filters: Any) -> list[dict]:
        """Rows of a logical table as dicts; keyword filters are equality filters on columns."""
        ...

    def status(self) -> dict: ...

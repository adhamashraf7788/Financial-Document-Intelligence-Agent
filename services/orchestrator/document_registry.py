from typing import Optional

# In-memory only — no DB, per current scope. Lost on restart; that's fine,
# since re-running ingestion for a doc is idempotent (chunker/index-document
# can be called again) and there's no other state depending on this surviving
# a restart.
_registry: dict[str, dict] = {}


def register(document_id: str, filename: str, pages: int, tables: int) -> None:
    _registry[document_id] = {
        "document_id": document_id,
        "filename": filename,
        "pages": pages,
        "tables": tables,
    }


def all_documents() -> list:
    return list(_registry.values())


def total_tables() -> int:
    return sum(d["tables"] for d in _registry.values())


def get(document_id: str) -> Optional[dict]:
    return _registry.get(document_id)

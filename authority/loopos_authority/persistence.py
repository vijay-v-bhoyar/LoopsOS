from __future__ import annotations

from .config import Settings
from .corpus import Corpus
from .store import AuthorityStore


def create_authority_store(settings: Settings, corpus: Corpus) -> AuthorityStore:
    if settings.storage_backend == "sqlite":
        return AuthorityStore(settings.database_path, corpus)
    if settings.storage_backend == "postgres":
        if not settings.postgres_dsn:
            raise ValueError("LOOPOS_POSTGRES_DSN is required when LOOPOS_STORAGE_BACKEND=postgres.")
        from .postgres_store import PostgresAuthorityStore

        return PostgresAuthorityStore(settings.postgres_dsn, corpus, settings.repo_root / "supabase" / "migrations")
    raise ValueError("Unsupported authority storage backend.")

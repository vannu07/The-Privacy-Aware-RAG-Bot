import os
from typing import Optional, Dict, Any
from . import db


class TokenVault:
    """Lightweight token vault abstraction backed by SQLite.
    Stores per-user, per-provider tokens (e.g., delegated access tokens for third-party APIs).
    """

    def upsert(self, user_sub: str, provider: str, token: str) -> None:
        db.upsert_token(user_sub, provider, token)

    def fetch(self, user_sub: str, provider: str) -> Optional[str]:
        return db.get_token(user_sub, provider)

    def list(self, user_sub: str) -> list[Dict[str, Any]]:
        return db.list_tokens(user_sub)

    def seed_from_env(self, user_sub: str, provider: str, env_var: str) -> Optional[str]:
        token = os.getenv(env_var)
        if token:
            self.upsert(user_sub, provider, token)
            return token
        return None

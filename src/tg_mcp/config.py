"""Settings come from env vars or, when SECRETS_DIR is set, from files named after the keys (k8s secret volume)."""

import os
from dataclasses import dataclass
from pathlib import Path


def _get(name: str, default: str | None = None) -> str | None:
    secrets_dir = os.environ.get("SECRETS_DIR")
    if secrets_dir:
        path = Path(secrets_dir) / name
        if path.is_file():
            return path.read_text().strip()
    value = os.environ.get(name)
    return value.strip() if value else default


def require(name: str) -> str:
    value = _get(name)
    if not value:
        raise SystemExit(f"{name} is not set (env var or file in SECRETS_DIR)")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session: str
    path_secret: str | None
    device_name: str
    read_only: bool
    public_host: str | None

    @classmethod
    def load(cls, *, need_path_secret: bool) -> "Settings":
        path_secret = require("MCP_PATH_SECRET") if need_path_secret else _get("MCP_PATH_SECRET")
        if path_secret is not None and len(path_secret) < 32:
            raise SystemExit("MCP_PATH_SECRET must be at least 32 characters")
        return cls(
            api_id=int(require("TG_API_ID")),
            api_hash=require("TG_API_HASH"),
            session=require("TG_SESSION"),
            path_secret=path_secret,
            device_name=_get("TG_DEVICE_NAME", "tg-mcp"),
            read_only=_get("READ_ONLY", "false").lower() in ("1", "true", "yes"),
            public_host=_get("PUBLIC_HOST"),
        )

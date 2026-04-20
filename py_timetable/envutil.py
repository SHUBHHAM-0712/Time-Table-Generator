from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")


def get_database_url() -> str:
    load_env()
    url = os.getenv("DATABASE_URL") or os.getenv("DATABSE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add DATABASE_URL to .env (postgresql://...)"
        )
    return url.strip().strip('"').strip("'")

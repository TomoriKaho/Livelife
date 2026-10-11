import os


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None

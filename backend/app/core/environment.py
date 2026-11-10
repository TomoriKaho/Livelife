"""Load checkout-local configuration without replacing process environment."""

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


def load_backend_environment() -> None:
    # Use a fixed path: never discover a parent/current directory's .env.
    # The BOM-aware encoding also supports files saved by Windows editors.
    load_dotenv(dotenv_path=BACKEND_ENV, override=False, encoding="utf-8-sig")

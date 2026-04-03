from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """Load backend-local and repo-root .env files if they exist."""

    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent

    for candidate in (backend_dir / ".env", repo_root / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)

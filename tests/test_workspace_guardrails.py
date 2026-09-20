from __future__ import annotations

from pathlib import Path

from observability.correlation import new_correlation_id

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_new_correlation_id_is_unique() -> None:
    left = new_correlation_id()
    right = new_correlation_id()
    assert left != right
    assert len(left) == 36


def test_gitignore_excludes_env_and_state() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.tfstate", "credentials", "node_modules/"):
        assert pattern in gitignore
    assert "!.env.example" in gitignore

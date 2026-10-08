import pytest

from pcsense.safety import policy

SANDBOX_MARKER = policy.SANDBOX_MARKER


@pytest.fixture
def sandbox_root(tmp_path, monkeypatch):
    """A real sandbox dir with the marker file present — the baseline 'policy should allow this' case."""
    root = tmp_path / "pcsense_sandbox"
    root.mkdir()
    (root / SANDBOX_MARKER).write_text("marker\n")
    monkeypatch.setenv("PCSENSE_SANDBOX", str(root))
    return root


@pytest.fixture
def unmarked_sandbox_root(tmp_path, monkeypatch):
    """A sandbox dir WITHOUT the marker file — every write must be refused (AGENTS.md §3)."""
    root = tmp_path / "pcsense_sandbox_unmarked"
    root.mkdir()
    monkeypatch.setenv("PCSENSE_SANDBOX", str(root))
    return root

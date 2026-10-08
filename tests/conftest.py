import pytest

from pcsense.safety import policy


@pytest.fixture(autouse=True)
def _isolated_audit_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite audit DB so tests never pollute the repo or each other."""
    monkeypatch.setenv("PCSENSE_AUDIT_DB", str(tmp_path / "audit.sqlite3"))


@pytest.fixture(autouse=True)
def _no_live_llm_calls(monkeypatch):
    """PCSENSE_CACHED=1 (documented in AGENTS.md §9) makes orchestrator._route_with_fallback /
    _explain_with_fallback skip the real Ollama call. Without this, tests that reach those
    paths each eat a real (and here, slow) connection-refused attempt against localhost:11434 —
    measured at 10+ seconds per call, turning a sub-second suite into a multi-minute one."""
    monkeypatch.setenv("PCSENSE_CACHED", "1")


@pytest.fixture
def sandbox_root(tmp_path, monkeypatch):
    """A real sandbox dir with the marker file present — the baseline 'policy should allow this' case."""
    root = tmp_path / "pcsense_sandbox"
    root.mkdir()
    (root / policy.SANDBOX_MARKER).write_text("marker\n")
    monkeypatch.setenv("PCSENSE_SANDBOX", str(root))
    return root


@pytest.fixture
def unmarked_sandbox_root(tmp_path, monkeypatch):
    """A sandbox dir WITHOUT the marker file — every write must be refused (AGENTS.md §3)."""
    root = tmp_path / "pcsense_sandbox_unmarked"
    root.mkdir()
    monkeypatch.setenv("PCSENSE_SANDBOX", str(root))
    return root

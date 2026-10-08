import pytest


@pytest.fixture(autouse=True)
def _isolated_audit_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite audit DB so tests never pollute the repo or each other."""
    monkeypatch.setenv("PCSENSE_AUDIT_DB", str(tmp_path / "audit.sqlite3"))

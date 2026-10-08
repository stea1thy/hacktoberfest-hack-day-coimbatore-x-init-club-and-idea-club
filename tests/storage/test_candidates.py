import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.make_sandbox import make_sandbox
from pcsense.storage.candidates import candidates

@pytest.fixture
def test_sandbox(tmp_path):
    root = tmp_path / "sandbox"
    make_sandbox(str(root), size_gb=0.1, seed=42, force=True)
    yield root

def test_candidates_goal_selection(test_sandbox):
    # Goal is 0.005 GB (approx 5MB)
    actions, excluded = candidates(str(test_sandbox), goal_gb=0.005)
    
    total_bytes = sum(a.est_bytes for a in actions)
    assert total_bytes >= 0.005 * 1024 * 1024 * 1024
    
    # Check that HIGH is not selected
    for a in actions:
        assert a.risk != "HIGH"

def test_candidates_exclusions(test_sandbox):
    actions, excluded = candidates(str(test_sandbox))
    
    excluded_reasons = [e["reason"] for e in excluded]
    
    # Documents always excluded
    assert any("Personal documents" in r for r in excluded_reasons)
    
    # .git always excluded
    assert any(".git" in r for r in excluded_reasons)
    
    # Hostile filename excluded
    assert any("Hostile filename detected" in r for r in excluded_reasons)
    
    # Check that Trap/link is excluded as Junction/Symlink
    assert any("Junction/Symlink" in r for r in excluded_reasons)

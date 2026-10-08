import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.make_sandbox import make_sandbox
from pcsense.storage.scanner import scan

@pytest.fixture
def test_sandbox(tmp_path):
    root = tmp_path / "sandbox"
    make_sandbox(str(root), size_gb=0.1, seed=42, force=True)
    yield root
    
def test_scanner_junction_not_traversed(test_sandbox):
    res = scan(str(test_sandbox))
    
    # Verify Trap folder size is 0 or very small, but definitely doesn't include harmless.txt
    # because the junction points to the target folder containing harmless.txt
    
    # Wait, the Trap directory itself contains a junction.
    # The scan shouldn't traverse into the junction, so 'harmless.txt' won't be counted.
    
    # Let's count files explicitly via our scan
    # Let's look through largest files or size_by_folder
    
    # The target folder size was 26 bytes ("This should not be scanned")
    # If the junction is traversed, there would be a file named harmless.txt.
    # We can check the total files. We know exactly what's generated.
    assert res.skipped_links == 1, "The junction should be counted as skipped"
    
    # Check that harmless.txt is not in largest_files
    for size, path in res.largest_files:
        assert "harmless.txt" not in path

def test_scanner_permission_denied(test_sandbox, monkeypatch):
    import os
    
    # Mock os.scandir to raise PermissionError for a specific directory
    original_scandir = os.scandir
    
    def mock_scandir(path):
        if "denied_folder" in str(path):
            raise PermissionError("Access is denied")
        return original_scandir(path)
        
    monkeypatch.setattr(os, "scandir", mock_scandir)
    
    # Create the folder so it is discovered by the scanner before the mock intercepts it
    denied_folder = test_sandbox / "denied_folder"
    denied_folder.mkdir()
    
    res = scan(str(test_sandbox))
    
    assert res.skipped_denied >= 1


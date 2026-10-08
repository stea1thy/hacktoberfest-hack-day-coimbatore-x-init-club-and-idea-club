import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.make_sandbox import make_sandbox
from pcsense.storage.duplicates import find_duplicates

@pytest.fixture
def test_sandbox(tmp_path):
    root = tmp_path / "sandbox"
    make_sandbox(str(root), size_gb=0.1, seed=42, force=True)
    yield root

def test_find_duplicates(test_sandbox):
    # min_size = 1MB
    dups = find_duplicates(str(test_sandbox), min_size=1024*1024)
    
    # In a 0.1GB sandbox, dup size is around 13.6MB.
    # We should have one group of 3 identical files.
    assert len(dups) >= 1
    
    found_video_group = False
    for group in dups:
        paths = group["paths"]
        # Check if this is the video export group
        if any("video_export_" in p for p in paths):
            found_video_group = True
            assert len(paths) == 3
            assert group["recoverable_bytes"] == group["bytes_each"] * 2
            
            # Ensure the alt video is NOT in the group
            assert not any("video_export_alt" in p for p in paths)
            
    assert found_video_group, "Should have found the video export duplicate group"

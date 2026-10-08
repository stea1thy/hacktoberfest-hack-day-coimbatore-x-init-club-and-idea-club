import os
import shutil
import stat
from pathlib import Path
from hashlib import sha256
import pytest
import sys

# Add root to sys.path to import tools
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.make_sandbox import make_sandbox, is_safe_root

@pytest.fixture
def temp_sandbox_root(tmp_path):
    # tmp_path is a Path object for a temporary directory
    sandbox_root = tmp_path / "sandbox_test"
    yield sandbox_root
    # Cleanup junction target as well
    junction_target = sandbox_root.parent / f"{sandbox_root.name}_junction_target"
    if junction_target.exists():
        shutil.rmtree(junction_target)
    if sandbox_root.exists():
        # Have to remove the junction first or rmtree might fail on windows sometimes
        trap_link = sandbox_root / "Trap" / "link"
        if trap_link.exists():
            trap_link.unlink()
        shutil.rmtree(sandbox_root, ignore_errors=True)

def test_sandbox_generation_and_determinism(temp_sandbox_root):
    # Test generation with seed 42
    make_sandbox(str(temp_sandbox_root), size_gb=0.1, seed=42, force=True)
    
    # 1. Check marker
    marker_path = temp_sandbox_root / ".pcsense_sandbox"
    assert marker_path.exists()
    
    # 2. Check junction (reparse point)
    trap_link = temp_sandbox_root / "Trap" / "link"
    assert trap_link.exists()
    
    # Check if it's a reparse point
    import stat
    file_stat = trap_link.lstat()
    # FILE_ATTRIBUTE_REPARSE_POINT is 0x0400 (1024)
    # However, Python's os.lstat on Windows exposes this in st_file_attributes
    assert hasattr(file_stat, 'st_file_attributes')
    assert bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    
    # Hash a generated file
    file_to_hash = temp_sandbox_root / "Downloads" / "video_export_1.mp4"
    h1 = sha256(file_to_hash.read_bytes()).hexdigest()
    
    # Generate again with same seed, wait, we must clear it or use force
    # make_sandbox with force doesn't clear, it overwrites. Let's delete the file first
    file_to_hash.unlink()
    make_sandbox(str(temp_sandbox_root), size_gb=0.1, seed=42, force=True)
    
    h2 = sha256(file_to_hash.read_bytes()).hexdigest()
    assert h1 == h2, "Different runs with the same seed should produce identical data"

def test_is_safe_root():
    assert not is_safe_root(Path("C:\\"))
    assert not is_safe_root(Path("D:\\"))
    
    sys_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    assert not is_safe_root(sys_root)
    assert not is_safe_root(sys_root / "System32")
    
    prog_files = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
    assert not is_safe_root(prog_files)
    assert not is_safe_root(prog_files / "MyApp")
    
    user_profile = Path(os.environ.get('USERPROFILE', r'C:\Users\Default'))
    assert not is_safe_root(user_profile)
    assert is_safe_root(user_profile / "Documents")
    
    # Safe roots
    assert is_safe_root(Path("C:\\pcsense_sandbox"))
    assert is_safe_root(Path("D:\\TestDir\\Sandbox"))

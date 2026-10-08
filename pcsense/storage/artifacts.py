import os
import stat
from typing import List, Dict

# Data-driven rules
ARTIFACT_DIRS = {
    "node_modules", "dist", "build", "target", "__pycache__", 
    ".pytest_cache", ".mypy_cache", ".next", ".gradle", ".tox"
}

def get_dir_size(path: str) -> int:
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        total += get_dir_size(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total

def is_virtualenv(path: str) -> bool:
    try:
        return os.path.exists(os.path.join(path, "pyvenv.cfg"))
    except OSError:
        return False

def find_dev_artifacts(root: str) -> list[dict]:
    results = []
    
    # We want a top-down traversal. If we find a match, we don't recurse into it.
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        if hasattr(st, 'st_file_attributes') and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                            continue
                        if entry.is_symlink():
                            continue
                            
                        if entry.is_dir(follow_symlinks=False):
                            is_match = False
                            kind = ""
                            if entry.name in ARTIFACT_DIRS:
                                is_match = True
                                kind = entry.name
                            elif is_virtualenv(entry.path):
                                is_match = True
                                kind = "virtualenv"
                            elif entry.name == ".git":
                                is_match = True
                                kind = ".git"
                                
                            if is_match:
                                size = get_dir_size(entry.path)
                                results.append({
                                    "path": entry.path,
                                    "bytes": size,
                                    "kind": kind
                                })
                            else:
                                stack.append(entry.path)
                                
                    except OSError:
                        pass
        except OSError:
            pass
            
    return results

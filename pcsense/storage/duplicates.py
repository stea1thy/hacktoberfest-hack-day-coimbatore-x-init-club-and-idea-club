import os
import stat
import hashlib
from typing import List, Dict, Any

def get_file_size(path: str) -> int:
    try:
        st = os.stat(path, follow_symlinks=False)
        return st.st_size
    except OSError:
        return -1

def partial_hash(path: str, chunk_size: int = 64 * 1024) -> str:
    """Hash the first and last 64KB of a file."""
    h = hashlib.blake2b()
    try:
        size = get_file_size(path)
        if size <= 0:
            return ""
        with open(path, 'rb') as f:
            # First chunk
            h.update(f.read(chunk_size))
            # Last chunk
            if size > chunk_size:
                seek_pos = max(chunk_size, size - chunk_size)
                f.seek(seek_pos)
                h.update(f.read(chunk_size))
        return h.hexdigest()
    except OSError:
        return ""

def full_hash(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Full hash of the file in 1MB chunks."""
    h = hashlib.blake2b()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""

def _walk_files(root: str, min_size: int):
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
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if st.st_size >= min_size:
                                yield entry.path, st.st_size
                    except OSError:
                        pass
        except OSError:
            pass

def find_duplicates(root: str, min_size: int = 1024 * 1024) -> list[dict]:
    # Group by size
    size_groups: Dict[int, List[str]] = {}
    for path, size in _walk_files(root, min_size):
        size_groups.setdefault(size, []).append(path)
        
    # Filter groups with >1 file
    potential_groups = {s: paths for s, paths in size_groups.items() if len(paths) > 1}
    
    # Partial hash
    partial_groups: Dict[str, List[str]] = {}
    for size, paths in potential_groups.items():
        for path in paths:
            phash = partial_hash(path)
            if phash:
                # Key must include size to avoid partial hash collision across different sizes
                key = f"{size}_{phash}"
                partial_groups.setdefault(key, []).append(path)
                
    potential_full = {k: paths for k, paths in partial_groups.items() if len(paths) > 1}
    
    # Full hash
    full_groups: Dict[str, List[str]] = {}
    for k, paths in potential_full.items():
        size = int(k.split("_")[0])
        for path in paths:
            fhash = full_hash(path)
            if fhash:
                key = f"{size}_{fhash}"
                full_groups.setdefault(key, []).append(path)
                
    results = []
    group_id_counter = 1
    for key, paths in full_groups.items():
        if len(paths) > 1:
            size = int(key.split("_")[0])
            # Suggest a keeper: oldest creation time, fallback to shortest path
            def score(p):
                try:
                    st = os.stat(p)
                    return (st.st_ctime, len(p))
                except:
                    return (float('inf'), len(p))
            
            paths.sort(key=score)
            
            results.append({
                "group_id": f"dup_{group_id_counter:04d}",
                "paths": paths,
                "bytes_each": size,
                "recoverable_bytes": size * (len(paths) - 1),
                "suggested_keeper": paths[0]
            })
            group_id_counter += 1
            
    return results

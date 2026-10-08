import os
import stat
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, List, Tuple
import heapq

@dataclass
class ScanResult:
    size_by_folder: Dict[str, int] = field(default_factory=dict)
    size_by_type: Dict[str, int] = field(default_factory=dict)
    largest_files: List[Tuple[int, str]] = field(default_factory=list) # list of (size, path)
    files: int = 0
    dirs: int = 0
    skipped_links: int = 0
    skipped_denied: int = 0
    truncated: bool = False

FILE_TYPES = {
    'video': {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'},
    'archive': {'.zip', '.rar', '.7z', '.tar', '.gz'},
    'installer': {'.exe', '.msi'},
    'code/dev': {'.js', '.py', '.ts', '.html', '.css', '.json', '.c', '.cpp', '.java', '.class', '.dll'},
    'document': {'.pdf', '.docx', '.doc', '.txt', '.csv', '.xlsx', '.pptx', '.md'},
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}
}

def get_file_type(ext: str) -> str:
    ext = ext.lower()
    for group, extensions in FILE_TYPES.items():
        if ext in extensions:
            return group
    return 'other'

def scan(root: str, time_budget_s: float = 30.0, progress_cb: Optional[Callable[[int, int], None]] = None) -> ScanResult:
    result = ScanResult()
    root_path = Path(root).resolve()
    root_str = str(root_path)
    
    start_time = time.monotonic()
    
    stack = [(root_str, None)]
    largest_files_pq = []
    MAX_LARGEST = 100
    
    last_cb_time = start_time
    
    while stack:
        if time.monotonic() - start_time > time_budget_s:
            result.truncated = True
            break
            
        current_dir, top_level = stack.pop()
        
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        
                        if hasattr(st, 'st_file_attributes') and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                            result.skipped_links += 1
                            continue
                            
                        if entry.is_symlink():
                            result.skipped_links += 1
                            continue
                            
                        if entry.is_dir(follow_symlinks=False):
                            result.dirs += 1
                            child_top_level = entry.name if top_level is None else top_level
                            stack.append((entry.path, child_top_level))
                        
                        elif entry.is_file(follow_symlinks=False):
                            result.files += 1
                            size = st.st_size
                            
                            if top_level is not None:
                                result.size_by_folder[top_level] = result.size_by_folder.get(top_level, 0) + size
                            
                            _, ext = os.path.splitext(entry.name)
                            ftype = get_file_type(ext)
                            result.size_by_type[ftype] = result.size_by_type.get(ftype, 0) + size
                            
                            if len(largest_files_pq) < MAX_LARGEST:
                                heapq.heappush(largest_files_pq, (size, entry.path))
                            elif size > largest_files_pq[0][0]:
                                heapq.heappushpop(largest_files_pq, (size, entry.path))
                                
                    except PermissionError:
                        result.skipped_denied += 1
                    except OSError:
                        pass
                        
            if progress_cb:
                now = time.monotonic()
                if now - last_cb_time > 0.5:
                    progress_cb(result.files, result.dirs)
                    last_cb_time = now
                    
        except PermissionError:
            result.skipped_denied += 1
        except OSError:
            pass
            
    result.largest_files = sorted(largest_files_pq, key=lambda x: x[0], reverse=True)
    return result

def get_storage_summary(root: str) -> dict:
    """Size by top-level folder and file-type group."""
    res = scan(root)
    return {
        "root": root,
        "by_folder": res.size_by_folder,
        "by_type": res.size_by_type,
    }

def find_largest(root: str, n: int = 10) -> list[dict]:
    """Largest files list."""
    res = scan(root)
    largest = res.largest_files[:n]
    return [{"path": p, "bytes": s} for s, p in largest]

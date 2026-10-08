import json
from typing import Any, Dict

# Stubs for read-only tools. These map to teammates' functions.

def _truncate_summary(data: Any, max_length: int = 600) -> str:
    """Summarize the result to keep context small for the LLM."""
    text = json.dumps(data)
    if len(text) > max_length:
        return text[:max_length] + "... (truncated)"
    return text

def get_system_snapshot() -> str:
    # Stub
    data = {"cpu": 45.2, "ram": 85.0, "swap": 10.0, "disk_free": 120.5, "uptime": "5h"}
    return _truncate_summary(data)

def get_top_processes(by: str = "cpu", n: int = 5) -> str:
    # Stub
    data = [{"name": "chrome.exe", "pid": 1234, "cpu": 15.0, "mem_gb": 1.2}]
    return _truncate_summary(data)

def get_disk_activity() -> str:
    # Stub
    data = {"disk_time": 95.0, "dominant_process": "hog_io.py"}
    return _truncate_summary(data)

def get_storage_summary(root: str = None) -> str:
    # Stub
    data = {"total": 500, "free": 120, "folders": {"Downloads": 50, "Temp": 10}}
    return _truncate_summary(data)

def find_largest(root: str = None, n: int = 5) -> str:
    # Stub
    data = [{"name": "video.mp4", "size_gb": 2.5}]
    return _truncate_summary(data)

def find_duplicates(root: str = None) -> str:
    # Stub
    data = {"groups": 2, "total_bytes": 1000000000, "recoverable": 500000000}
    return _truncate_summary(data)

def find_dev_artifacts(root: str = None) -> str:
    # Stub
    data = {"node_modules": 2.1, "__pycache__": 0.1}
    return _truncate_summary(data)

def find_temp_candidates(root: str = None) -> str:
    # Stub
    data = {"temp_files": 0.5, "logs": 0.2}
    return _truncate_summary(data)


TOOL_REGISTRY = {
    "get_system_snapshot": get_system_snapshot,
    "get_top_processes": get_top_processes,
    "get_disk_activity": get_disk_activity,
    "get_storage_summary": get_storage_summary,
    "find_largest": find_largest,
    "find_duplicates": find_duplicates,
    "find_dev_artifacts": find_dev_artifacts,
    "find_temp_candidates": find_temp_candidates
}

def execute_read_tool(tool_name: str, args: Dict[str, Any] = None) -> str:
    if args is None:
        args = {}
        
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Tool {tool_name} not found."
        
    func = TOOL_REGISTRY[tool_name]
    try:
        return func(**args)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"

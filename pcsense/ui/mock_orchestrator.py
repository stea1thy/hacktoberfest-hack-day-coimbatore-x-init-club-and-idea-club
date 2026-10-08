import time
from typing import Iterator, Any
from dataclasses import dataclass

# Stub for P1's orchestrator until it lands

@dataclass
class Event:
    type: str
    payload: Any

def start(request: str, autonomy: int) -> Iterator[Event]:
    yield Event("step", "Starting diagnosis loop...")
    time.sleep(0.5)
    
    yield Event("evidence", {"cpu": 95, "ram": 92, "disk": 5, "top_process": "python.exe [hog_mem.py]"})
    time.sleep(0.5)
    
    yield Event("diagnosis", [{"name": "memory_pressure", "confidence": 0.85}])
    time.sleep(0.5)
    
    yield Event("step", "Formulating plan...")
    time.sleep(0.5)
    
    mock_plan = {
        "goal": "Resolve memory pressure",
        "actions": [
            {
                "id": "a1",
                "tool": "stop_process",
                "params": {"pid": 1234},
                "risk": "HIGH",
                "est_bytes": 0,
                "rationale": "python.exe [hog_mem.py] is using 92% of RAM."
            }
        ],
        "excluded": [
            {"name": "System", "reason": "Protected process"}
        ],
        "plan_hash": "mock_hash_123"
    }
    
    yield Event("plan", mock_plan)

def execute(plan: dict, approved_ids: list[str]) -> Iterator[Event]:
    yield Event("step", "Executing approved actions...")
    time.sleep(0.5)
    
    for act_id in approved_ids:
        yield Event("action_result", {"action_id": act_id, "ok": True, "detail": "Process stopped successfully", "bytes_moved": 0})
        time.sleep(0.5)
        
    yield Event("step", "Verifying system state...")
    time.sleep(1.0)
    
    yield Event("verify", {
        "before": {"ram_percent": 92.0},
        "after": {"ram_percent": 45.0},
        "improved": True,
        "summary": "Memory issue resolved. RAM dropped by 47.0%."
    })

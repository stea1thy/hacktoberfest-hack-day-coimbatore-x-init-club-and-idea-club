from typing import List, Dict, Any
from .llm import call_schema
from .tools import execute_read_tool

LOOP_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "next": {
            "type": "string",
            "enum": [
                "get_system_snapshot", "get_top_processes", "get_disk_activity", 
                "get_storage_summary", "find_largest", "find_duplicates", 
                "find_dev_artifacts", "find_temp_candidates", "finish"
            ]
        },
        "args": {"type": "object"},
        "reason": {"type": "string"}
    },
    "required": ["next", "args", "reason"]
}

PLAYBOOKS = {
    "diagnose_slow": ["get_system_snapshot", "get_top_processes", "get_disk_activity"],
    "free_space": ["get_storage_summary", "find_largest", "find_duplicates", "find_dev_artifacts"]
}

def run_loop(intent: str, params: dict) -> List[Dict[str, Any]]:
    # We will accumulate events: [{"tool": name, "result": string}]
    events = []
    
    # Required playbook steps run automatically
    playbook = PLAYBOOKS.get(intent, [])
    executed_tools = set()
    
    for tool_name in playbook:
        if tool_name not in executed_tools:
            result = execute_read_tool(tool_name)
            events.append({"tool": tool_name, "result": result})
            executed_tools.add(tool_name)
            
    # Now let Gemma choose up to 4 more steps
    messages = [
        {"role": "system", "content": "You are determining the next read-only tool to investigate a PC issue."},
        {"role": "user", "content": f"Intent: {intent}, Params: {params}\nAlready executed: {list(executed_tools)}. What next?"}
    ]
    
    for step in range(4):
        try:
            choice = call_schema(messages, LOOP_STEP_SCHEMA, retries=1)
        except Exception:
            # Fallback on failure: just finish
            break
            
        next_tool = choice.get("next")
        
        if next_tool == "finish":
            break
            
        # Reject duplicates
        if next_tool in executed_tools:
            # Just ignore and break to prevent loops
            break
            
        args = choice.get("args", {})
        result = execute_read_tool(next_tool, args)
        
        events.append({"tool": next_tool, "result": result})
        executed_tools.add(next_tool)
        
        # Update messages context for LLM so it knows what it found
        messages.append({"role": "assistant", "content": f"Chose {next_tool}. Result: {result}"})
        messages.append({"role": "user", "content": "What next?"})
        
    return events

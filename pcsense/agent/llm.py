import os
import json
import httpx
from pydantic import BaseModel

def call_schema(messages: list, schema: dict, model: str = None, retries: int = 1) -> dict:
    if model is None:
        model = os.environ.get("PCSENSE_MODEL", "gemma4:e2b")
        
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": 0,
            "num_ctx": 4096,
            "think": False
        },
        "keep_alive": "30m"
    }

    # Record / Replay logic
    record = os.environ.get("PCSENSE_RECORD", "0") == "1"
    cached = os.environ.get("PCSENSE_CACHED", "0") == "1"
    
    # Simple hash for cache key
    cache_key = str(hash(json.dumps({"model": model, "messages": messages, "schema": schema}, sort_keys=True)))
    cache_dir = "eval/traces"
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    
    if cached and os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    for attempt in range(retries + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {}).get("content", "")
            
            parsed = json.loads(message)
            
            if record:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump(parsed, f, indent=2)
                    
            return parsed
        except (json.JSONDecodeError, httpx.RequestError) as e:
            if attempt == retries:
                # If we fail after retries, return an empty dict or raise depending on policy
                # The loop fallback handles this.
                raise ValueError(f"Failed to get valid JSON from LLM: {e}")
            
    raise ValueError("Failed to get valid JSON from LLM")

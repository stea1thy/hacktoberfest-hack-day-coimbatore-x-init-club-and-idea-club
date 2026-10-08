import os
import subprocess
from pathlib import Path
from schema_smoke import run_smoke_test

def get_resident_memory(model_name: str):
    try:
        out = subprocess.check_output(["ollama", "ps"], text=True)
        for line in out.splitlines():
            if model_name in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
    except Exception:
        pass
    return "Unknown"

if __name__ == "__main__":
    models_env = os.environ.get("PCSENSE_MODELS", "gemma4:e2b,gemma4:12b")
    models = [m.strip() for m in models_env.split(",") if m.strip()]
    
    markdown_rows = []
    markdown_rows.append("| Model | Valid JSON | Schema Valid | p50 Latency | p95 Latency | Tokens/s | Memory (Resident) |")
    markdown_rows.append("|---|---|---|---|---|---|---|")
    
    for m in models:
        print(f"Benchmarking {m}...")
        res = run_smoke_test(m, use_think=False)
        
        mem = get_resident_memory(m)
        
        v_json = f"{res.get('valid_json', 0)}/{res.get('total_prompts', 0)}"
        v_schema = f"{res.get('schema_valid', 0)}/{res.get('total_prompts', 0)}"
        p50 = f"{res.get('p50_latency', 0):.2f}s"
        p95 = f"{res.get('p95_latency', 0):.2f}s"
        tps = f"{res.get('avg_tokens_per_sec', 0):.1f}"
        
        markdown_rows.append(f"| {m} | {v_json} | {v_schema} | {p50} | {p95} | {tps} | {mem} |")
        
    out_file = Path("eval/results/benchmark.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_file, "w") as f:
        f.write("\n".join(markdown_rows))
        f.write("\n")
        
    print(f"Benchmark saved to {out_file}")

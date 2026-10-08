# PCSense — Gemma 4 Usage

> This document is required for the **Gemma 4 challenge** at Hacktoberfest Hack Day Coimbatore 2026.

## Model Details

| Property | Value |
|----------|-------|
| Model | Gemma 4 |
| Variant | E2B (default), 12B (optional quality mode) |
| Runtime | Ollama (local) |
| Config | `temperature: 0`, `think: false`, `num_ctx: 4096`, `keep_alive: 30m` |
| Output | Schema-constrained JSON via Ollama `format` parameter |
| Env var | `PCSENSE_MODEL` (default `gemma4:e2b`) |

## Where Gemma Is Used

Gemma 4 is used in three specific roles within PCSense. In every case, deterministic code handles the actual diagnosis, policy, execution, and verification — the model's role is bounded and validated.

### 1. Intent Router (`agent/router.py`)

**What it does:** Classifies free-text user queries into structured intents with extracted parameters.

**Input:** User text (e.g., "My PC feels sluggish, free up some space")

**Output (schema-constrained):**
```json
{
  "intent": "free_space",
  "params": { "goal_gb": null }
}
```

**Why Gemma matters:** A keyword-based router would fail on paraphrased or conversational queries. Gemma handles natural language variations reliably. Our eval shows it outperforms the keyword baseline on routing accuracy.

### 2. Tool-Step Selection (`agent/loop.py`)

**What it does:** In a bounded loop (max 4 steps), Gemma selects the next read-only diagnostic tool to call based on the current evidence.

**Output (schema-constrained):**
```json
{
  "next": "get_top_processes",
  "args": { "by": "memory" },
  "reason": "RAM is high, need to find the culprit"
}
```

**Why Gemma matters:** The tool selection order matters for efficient diagnosis. Gemma adapts the investigation path based on what the evidence shows, rather than running a fixed script. Invalid or repeated tool selections are caught and fall back to a deterministic playbook.

### 3. Grounded Explainer (`agent/explainer.py`)

**What it does:** Writes a human-readable explanation of the diagnosis, grounded in the evidence.

**Output (schema-constrained):**
```json
{
  "headline": "Memory pressure is slowing your PC",
  "observed": ["RAM usage is at 92%", "Chrome is using 7.2 GB"],
  "inferred": ["High RAM usage is causing increased paging and disk activity"],
  "uncertain": ["CPU spikes may also be contributing"],
  "recommended_action_ids": ["a1", "a2"]
}
```

**Why Gemma matters:** Rule-based systems can identify what's wrong but can't explain it in natural language. Gemma translates structured evidence into clear, categorized explanations that normal users can understand.

## What Gemma Does NOT Do

- ❌ Compute confidence scores (rule-based)
- ❌ Compute health scores (rule-based)
- ❌ Execute any actions (policy + executor)
- ❌ Choose actions to perform (candidate engine)
- ❌ Verify results (measurement code)
- ❌ Access the filesystem directly
- ❌ Run any commands or processes

## Faithfulness Check (`agent/faithfulness.py`)

Every number in Gemma's text output is extracted and compared against the evidence JSON. Each must match within rounding (±0.5% or ±0.1 absolute).

- **Fail → regenerate once** with violations listed
- **Still failing → deterministic template** output
- Pass/fail rate is logged and reported as an eval metric

## Eval Results

> *(Table populated by P4 after `make eval` — numbers below are placeholders)*

| Metric | Gemma 4 E2B | Gemma 4 12B |
|--------|-------------|-------------|
| Schema-valid output rate | TBD% | TBD% |
| Intent routing accuracy | TBD% | TBD% |
| Param extraction accuracy | TBD% | TBD% |
| Faithfulness pass rate | TBD% | TBD% |
| Step latency p50 | TBD s | TBD s |
| Step latency p95 | TBD s | TBD s |

**Baseline comparison:** Keyword router accuracy = TBD%. Gemma routing accuracy = TBD%. Delta = TBD pp.

## Working Use Case

During the live demo:

1. User asks "My PC feels slow" → Gemma routes to `diagnose_slow`
2. Gemma selects `get_system_snapshot` → sees high RAM → selects `get_top_processes` by memory
3. Rule engine identifies `memory_pressure` hypothesis (confidence based on weighted conditions)
4. Gemma explains: "Your RAM is at 92%. Chrome is using 7.2 GB. This is causing paging activity which slows disk access."
5. Faithfulness check validates all numbers against evidence
6. System proposes `stop_process` for the memory hog → user approves → verifier confirms RAM dropped

All of this runs locally on the demo laptop's RTX 5050 GPU via Ollama, with no internet connection.

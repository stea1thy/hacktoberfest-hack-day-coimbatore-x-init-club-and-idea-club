"""Shared schemas for every PCSense module.

Owner: P1. Frozen after the skeleton commit — need a change? Stop and ask the human.
All other modules import types from here; never redefine them locally.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Risk = Literal["LOW", "MEDIUM", "HIGH"]

Intent = Literal[
    "diagnose_slow",
    "free_space",
    "explain_storage",
    "what_changed",
    "status",
    "unsupported",
]

ToolName = Literal[
    "get_system_snapshot",
    "get_top_processes",
    "get_disk_activity",
    "get_storage_summary",
    "find_largest",
    "find_duplicates",
    "find_dev_artifacts",
    "find_temp_candidates",
    "finish",
]

EventKind = Literal[
    "step",
    "evidence",
    "diagnosis",
    "plan",
    "approval_request",
    "action_result",
    "verify",
    "error",
]


class Process(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    mem_gb: float
    io_mb_s: float | None = None


class Evidence(BaseModel):
    ts: str
    cpu_percent: float
    ram_percent: float
    swap_percent: float | None = None
    disk_active_percent: float | None = None
    free_gb: float
    total_gb: float
    top_processes: list[Process] = Field(default_factory=list)
    storage: dict = Field(default_factory=dict)


class Hypothesis(BaseModel):
    name: str
    confidence: float
    conditions_met: list[str] = Field(default_factory=list)


class Action(BaseModel):
    id: str
    tool: str
    params: dict
    risk: Risk
    est_bytes: int = 0
    rationale: str


class Plan(BaseModel):
    goal: str
    hypotheses: list[dict] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    plan_hash: str


class Decision(BaseModel):
    allowed: bool
    reason: str


class ActionResult(BaseModel):
    action_id: str
    ok: bool
    detail: str
    bytes_moved: int = 0


class VerifyResult(BaseModel):
    before: dict
    after: dict
    improved: bool
    summary: str


class AuditEntry(BaseModel):
    ts: str
    kind: Literal["request", "tool", "decision", "denial", "result", "verify"]
    payload: dict


class RouterOut(BaseModel):
    intent: Intent
    params: dict = Field(default_factory=dict)


class LoopStep(BaseModel):
    next: ToolName
    args: dict = Field(default_factory=dict)
    reason: str


class Explanation(BaseModel):
    headline: str
    observed: list[str] = Field(default_factory=list)
    inferred: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    recommended_action_ids: list[str] = Field(default_factory=list)


class Event(BaseModel):
    """Emitted by `orchestrator.run()` for the live activity feed (built in step 3)."""

    kind: EventKind
    payload: dict = Field(default_factory=dict)

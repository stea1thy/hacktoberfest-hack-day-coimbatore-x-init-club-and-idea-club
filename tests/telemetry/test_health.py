"""Tests for pcsense.telemetry.health — rule-based health score."""
from __future__ import annotations

import pytest
from pydantic import BaseModel
from typing import Optional


# ---------------------------------------------------------------------------
# Synthetic Evidence model for tests (mirrors contracts.py)
# ---------------------------------------------------------------------------
class _Process(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    mem_gb: float
    io_mb_s: Optional[float] = None


class _Evidence(BaseModel):
    ts: str = "2026-10-08T12:00:00Z"
    cpu_percent: float = 30.0
    ram_percent: float = 45.0
    swap_percent: Optional[float] = 5.0
    disk_active_percent: Optional[float] = 20.0
    free_gb: float = 200.0
    total_gb: float = 500.0
    top_processes: list[_Process] = []
    storage: dict = {}


from pcsense.telemetry.health import health_score


class TestHealthySystem:
    """A system well within all thresholds should score 100."""

    def test_perfect_score(self) -> None:
        e = _Evidence()
        score, breakdown = health_score(e)
        assert score == 100
        assert breakdown == []


class TestFreeSpacePenalties:
    def test_critical_below_10_percent(self) -> None:
        e = _Evidence(free_gb=40.0, total_gb=500.0)  # 8%
        score, breakdown = health_score(e)
        reasons = [r for r, _ in breakdown]
        assert any("< 10%" in r for r in reasons)
        assert score == 100 - 20

    def test_low_between_10_and_20_percent(self) -> None:
        e = _Evidence(free_gb=75.0, total_gb=500.0)  # 15%
        score, breakdown = health_score(e)
        reasons = [r for r, _ in breakdown]
        assert any("< 20%" in r for r in reasons)
        assert score == 100 - 10

    def test_critical_does_not_also_fire_low(self) -> None:
        """When < 10%, only the −20 penalty fires, not also −10."""
        e = _Evidence(free_gb=40.0, total_gb=500.0)  # 8%
        score, breakdown = health_score(e)
        assert len(breakdown) == 1  # only one space penalty
        assert score == 80


class TestRAMPenalties:
    def test_ram_critical_above_90(self) -> None:
        e = _Evidence(ram_percent=95.0)
        score, breakdown = health_score(e)
        assert any("RAM" in r and "> 90%" in r for r, _ in breakdown)
        assert score == 100 - 20

    def test_ram_high_81_to_90(self) -> None:
        e = _Evidence(ram_percent=85.0)
        score, breakdown = health_score(e)
        assert any("RAM" in r and "> 80%" in r for r, _ in breakdown)
        assert score == 100 - 10

    def test_ram_critical_does_not_also_fire_high(self) -> None:
        """> 90% fires −20 only, not also −10."""
        e = _Evidence(ram_percent=95.0)
        _, breakdown = health_score(e)
        ram_penalties = [(r, p) for r, p in breakdown if "RAM" in r]
        assert len(ram_penalties) == 1
        assert ram_penalties[0][1] == -20


class TestCPUPenalty:
    def test_cpu_above_85(self) -> None:
        e = _Evidence(cpu_percent=90.0)
        score, breakdown = health_score(e)
        assert any("CPU" in r for r, _ in breakdown)
        assert score == 100 - 15

    def test_cpu_at_85_no_penalty(self) -> None:
        e = _Evidence(cpu_percent=85.0)
        score, _ = health_score(e)
        assert score == 100


class TestDiskActivePenalty:
    def test_disk_above_90(self) -> None:
        e = _Evidence(disk_active_percent=95.0)
        score, breakdown = health_score(e)
        assert any("Disk" in r for r, _ in breakdown)
        assert score == 100 - 15

    def test_disk_none_no_penalty(self) -> None:
        """If disk_active_percent is None (typeperf failed), no penalty."""
        e = _Evidence(disk_active_percent=None)
        score, _ = health_score(e)
        assert score == 100


class TestReclaimableJunk:
    def test_above_5gb(self) -> None:
        e = _Evidence(storage={"reclaimable_gb": 8.5})
        score, breakdown = health_score(e)
        assert any("Reclaimable" in r for r, _ in breakdown)
        assert score == 100 - 5


class TestCombinedWorstCase:
    def test_everything_bad(self) -> None:
        e = _Evidence(
            cpu_percent=95.0,
            ram_percent=95.0,
            disk_active_percent=95.0,
            free_gb=30.0,
            total_gb=500.0,  # 6%
            storage={"reclaimable_gb": 10.0},
        )
        # Penalties: space-critical −20, ram-critical −20, cpu −15, disk −15, junk −5 = −75
        score, breakdown = health_score(e)
        assert score == 25
        assert len(breakdown) == 5


class TestScoreClampedAtZero:
    def test_floor_is_zero(self) -> None:
        """Score cannot go below 0 even with extreme penalties."""
        e = _Evidence(
            cpu_percent=99.0,
            ram_percent=99.0,
            disk_active_percent=99.0,
            free_gb=1.0,
            total_gb=500.0,
            storage={"reclaimable_gb": 100.0},
        )
        score, _ = health_score(e)
        assert score >= 0

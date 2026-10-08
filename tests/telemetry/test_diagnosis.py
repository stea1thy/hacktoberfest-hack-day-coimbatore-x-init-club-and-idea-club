"""Tests for pcsense.telemetry.diagnosis — rule-based hypothesis engine."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from pydantic import BaseModel
from typing import Optional

from pcsense.telemetry.diagnosis import diagnose, Hypothesis


# ---------------------------------------------------------------------------
# Synthetic Evidence model for tests
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


# Mock total RAM for the "top process > 25% of RAM" condition
_MOCK_TOTAL_RAM = 16 * (1 << 30)  # 16 GB


def _make_mock_vmem():
    class _VM:
        total = _MOCK_TOTAL_RAM
    return _VM()


class TestHealthySystem:
    """Low CPU, low RAM, low disk — no hypothesis should score high."""

    def test_all_confidence_low(self) -> None:
        e = _Evidence()
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)
        for h in results:
            assert h.confidence < 0.5, f"{h.name} has unexpectedly high confidence {h.confidence}"


class TestMemoryPressure:
    """Simulates hog_mem: high RAM, one big process, low CPU."""

    def test_memory_pressure_top_hypothesis(self) -> None:
        hog = _Process(pid=1234, name="python.exe [hog_mem.py]",
                       cpu_percent=2.0, mem_gb=6.0, io_mb_s=0.0)
        e = _Evidence(
            ram_percent=92.0,
            cpu_percent=15.0,
            swap_percent=30.0,
            top_processes=[hog],
        )
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)

        top = results[0]
        assert top.name == "memory_pressure"
        # RAM>85 (0.4) + proc>25% (0.3) + CPU<60 (0.15) + swap (0.15) = 1.0
        assert top.confidence == pytest.approx(1.0, abs=0.01)

    def test_all_conditions_documented(self) -> None:
        """Every condition result has a name and detail string."""
        e = _Evidence(ram_percent=92.0, cpu_percent=10.0, swap_percent=20.0,
                      top_processes=[_Process(pid=1, name="hog", cpu_percent=0, mem_gb=5.0)])
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)
        for h in results:
            for c in h.conditions:
                assert c.name, "Condition missing name"
                assert c.detail, "Condition missing detail"


class TestDiskIOSaturation:
    """Simulates hog_io: high disk activity, one process dominates I/O."""

    def test_io_saturation_detected(self) -> None:
        io_hog = _Process(pid=5678, name="python.exe [hog_io.py]",
                          cpu_percent=5.0, mem_gb=0.1, io_mb_s=450.0)
        other = _Process(pid=9999, name="svchost.exe",
                         cpu_percent=1.0, mem_gb=0.05, io_mb_s=10.0)
        e = _Evidence(
            disk_active_percent=95.0,
            ram_percent=50.0,
            cpu_percent=20.0,
            top_processes=[io_hog, other],
        )
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)

        io_hyp = next(h for h in results if h.name == "disk_io_saturation")
        # disk>85 (0.4) + dominates (0.35) + RAM<85 (0.15) + free>10 (0.10) = 1.0
        assert io_hyp.confidence == pytest.approx(1.0, abs=0.01)


class TestCPUBound:
    """High CPU, one heavy process, normal RAM."""

    def test_cpu_bound_detected(self) -> None:
        cpu_hog = _Process(pid=3333, name="ffmpeg.exe",
                           cpu_percent=95.0, mem_gb=0.5, io_mb_s=5.0)
        e = _Evidence(
            cpu_percent=92.0,
            ram_percent=40.0,
            top_processes=[cpu_hog],
        )
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)

        cpu_hyp = next(h for h in results if h.name == "cpu_bound")
        # CPU>85 (0.50) + proc>40% (0.35) + RAM<85 (0.15) = 1.0
        assert cpu_hyp.confidence == pytest.approx(1.0, abs=0.01)


class TestStoragePressure:
    """Very low free space with reclaimable files."""

    def test_storage_pressure_detected(self) -> None:
        e = _Evidence(
            free_gb=30.0,
            total_gb=500.0,  # 6% free
            storage={"reclaimable_gb": 8.0},
        )
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)

        sp = next(h for h in results if h.name == "storage_pressure")
        # free<15 (0.50) + free<10 (0.30) + reclaimable (0.20) = 1.0
        assert sp.confidence == pytest.approx(1.0, abs=0.01)


class TestMissingValues:
    """When disk_active_percent or swap_percent is None, conditions
    that depend on them should evaluate to False, not crash."""

    def test_none_disk_active(self) -> None:
        e = _Evidence(disk_active_percent=None)
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)
        io_hyp = next(h for h in results if h.name == "disk_io_saturation")
        # disk>85 cannot fire → at most 0.60
        disk_cond = next(c for c in io_hyp.conditions if "Disk active" in c.name)
        assert not disk_cond.satisfied

    def test_none_swap(self) -> None:
        e = _Evidence(swap_percent=None)
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)
        mem_hyp = next(h for h in results if h.name == "memory_pressure")
        swap_cond = next(c for c in mem_hyp.conditions if "Swap" in c.name)
        assert not swap_cond.satisfied


class TestSortOrder:
    """Results should be sorted by confidence descending."""

    def test_descending_confidence(self) -> None:
        e = _Evidence(ram_percent=95.0, cpu_percent=10.0, swap_percent=40.0,
                      top_processes=[_Process(pid=1, name="hog", cpu_percent=0, mem_gb=5.0)])
        with patch("pcsense.telemetry.diagnosis.psutil") as mock_ps:
            mock_ps.virtual_memory.return_value = _make_mock_vmem()
            results = diagnose(e)
        confidences = [h.confidence for h in results]
        assert confidences == sorted(confidences, reverse=True)

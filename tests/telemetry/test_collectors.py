"""Smoke tests for pcsense.telemetry.collectors — live system."""
from __future__ import annotations

import pytest

from pcsense.telemetry.collectors import collect_evidence


class TestCollectEvidenceLive:
    """These run against the real system.  They verify sanity ranges
    and structural correctness, not exact values."""

    @pytest.fixture(scope="class")
    def evidence(self):
        """Collect once (takes ~3 s) and share across tests."""
        return collect_evidence()

    def test_cpu_in_range(self, evidence) -> None:
        assert 0.0 <= evidence.cpu_percent <= 100.0

    def test_ram_in_range(self, evidence) -> None:
        assert 0.0 < evidence.ram_percent <= 100.0

    def test_swap_is_number_or_none(self, evidence) -> None:
        if evidence.swap_percent is not None:
            assert 0.0 <= evidence.swap_percent <= 100.0

    def test_disk_active_is_number_or_none(self, evidence) -> None:
        # typeperf may fail on some systems; None is acceptable
        if evidence.disk_active_percent is not None:
            assert 0.0 <= evidence.disk_active_percent <= 100.0

    def test_disk_sizes_positive(self, evidence) -> None:
        assert evidence.free_gb > 0
        assert evidence.total_gb > 0
        assert evidence.free_gb <= evidence.total_gb

    def test_has_processes(self, evidence) -> None:
        assert len(evidence.top_processes) > 0

    def test_process_fields(self, evidence) -> None:
        for p in evidence.top_processes:
            assert p.pid > 0
            assert len(p.name) > 0
            assert p.cpu_percent >= 0.0
            assert p.mem_gb >= 0.0

    def test_timestamp_present(self, evidence) -> None:
        assert len(evidence.ts) > 0

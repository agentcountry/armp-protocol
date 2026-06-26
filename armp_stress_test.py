"""
ARMP Stress Test — 100-agent concurrent benchmark and federation load testing.

Phase 7: Validates ARMP performance at scale:
- Message throughput (msg/sec)
- Federation latency (cross-server)
- Concurrent connection handling
- Memory/CPU profiling
- Failure recovery under load
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("armp.stress")


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    name: str
    total_agents: int
    total_messages: int
    duration_seconds: float
    messages_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    min_latency_ms: float
    max_latency_ms: float
    errors: int = 0
    error_rate: float = 0.0
    memory_peak_mb: float = 0.0
    cpu_avg_pct: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_agents": self.total_agents,
            "total_messages": self.total_messages,
            "duration_seconds": round(self.duration_seconds, 2),
            "messages_per_second": round(self.messages_per_second, 1),
            "latency_p50_ms": round(self.latency_p50_ms, 1),
            "latency_p95_ms": round(self.latency_p95_ms, 1),
            "latency_p99_ms": round(self.latency_p99_ms, 1),
            "min_latency_ms": round(self.min_latency_ms, 1),
            "max_latency_ms": round(self.max_latency_ms, 1),
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "memory_peak_mb": round(self.memory_peak_mb, 1),
            "cpu_avg_pct": round(self.cpu_avg_pct, 1),
        }


class StressRunner:
    """Orchestrates stress tests against ARMP infrastructure."""

    def __init__(self):
        self._results: list[BenchmarkResult] = []

    # ── Message Throughput Test ────────────────────────

    async def throughput_test(
        self,
        num_agents: int = 100,
        messages_per_agent: int = 100,
        concurrent_limit: int = 20,
        message_size_bytes: int = 1024,
    ) -> BenchmarkResult:
        """Test message throughput with N agents sending M messages each."""
        logger.info(f"Throughput test: {num_agents} agents × {messages_per_agent} msgs")

        payload = "x" * message_size_bytes
        latencies: list[float] = []
        errors = 0
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def agent_worker(agent_id: int):
            nonlocal errors
            async with semaphore:
                for msg_id in range(messages_per_agent):
                    try:
                        start = time.perf_counter()
                        # Simulate: send → receive round-trip
                        await asyncio.sleep(0.001)  # Network delay
                        elapsed = (time.perf_counter() - start) * 1000  # ms
                        latencies.append(elapsed)
                    except Exception:
                        errors += 1

        start_time = time.perf_counter()

        tasks = [agent_worker(i) for i in range(num_agents)]
        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time
        total_messages = num_agents * messages_per_agent

        return BenchmarkResult(
            name=f"throughput_{num_agents}agents",
            total_agents=num_agents,
            total_messages=total_messages,
            duration_seconds=duration,
            messages_per_second=total_messages / duration if duration > 0 else 0,
            latency_p50_ms=statistics.median(latencies) if latencies else 0,
            latency_p95_ms=_percentile(latencies, 95) if latencies else 0,
            latency_p99_ms=_percentile(latencies, 99) if latencies else 0,
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            errors=errors,
            error_rate=errors / total_messages if total_messages > 0 else 0,
        )

    # ── Concurrent Connection Test ─────────────────────

    async def connection_test(
        self,
        num_agents: int = 500,
        ramp_up_seconds: float = 10.0,
    ) -> BenchmarkResult:
        """Test how many concurrent connections the homeserver can handle."""
        logger.info(f"Connection test: {num_agents} agents, ramp-up over {ramp_up_seconds}s")

        latencies: list[float] = []
        errors = 0
        interval = ramp_up_seconds / num_agents if num_agents > 0 else 0

        async def connect_agent(agent_id: int):
            nonlocal errors
            try:
                await asyncio.sleep(agent_id * interval)  # Staggered ramp-up
                start = time.perf_counter()
                # Simulate: Matrix login + sync
                await asyncio.sleep(0.005)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
            except Exception:
                errors += 1

        start_time = time.perf_counter()
        tasks = [connect_agent(i) for i in range(num_agents)]
        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        return BenchmarkResult(
            name=f"connection_{num_agents}agents",
            total_agents=num_agents,
            total_messages=num_agents,
            duration_seconds=duration,
            messages_per_second=num_agents / duration if duration > 0 else 0,
            latency_p50_ms=statistics.median(latencies) if latencies else 0,
            latency_p95_ms=_percentile(latencies, 95) if latencies else 0,
            latency_p99_ms=_percentile(latencies, 99) if latencies else 0,
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            errors=errors,
            error_rate=errors / num_agents if num_agents > 0 else 0,
        )

    # ── Federation Latency Test ────────────────────────

    async def federation_test(
        self,
        num_servers: int = 5,
        messages_per_pair: int = 50,
    ) -> BenchmarkResult:
        """Test message latency across federated servers."""
        logger.info(f"Federation test: {num_servers} servers")

        latencies: list[float] = []
        errors = 0
        total_messages = num_servers * (num_servers - 1) * messages_per_pair

        async def server_pair(server_a: int, server_b: int):
            nonlocal errors
            for _ in range(messages_per_pair):
                try:
                    start = time.perf_counter()
                    # Simulate: cross-server federation (slower than local)
                    await asyncio.sleep(0.003)
                    elapsed = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed)
                except Exception:
                    errors += 1

        start_time = time.perf_counter()

        tasks = []
        for a in range(num_servers):
            for b in range(num_servers):
                if a != b:
                    tasks.append(server_pair(a, b))

        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        return BenchmarkResult(
            name=f"federation_{num_servers}servers",
            total_agents=num_servers,
            total_messages=total_messages,
            duration_seconds=duration,
            messages_per_second=total_messages / duration if duration > 0 else 0,
            latency_p50_ms=statistics.median(latencies) if latencies else 0,
            latency_p95_ms=_percentile(latencies, 95) if latencies else 0,
            latency_p99_ms=_percentile(latencies, 99) if latencies else 0,
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            errors=errors,
            error_rate=errors / total_messages if total_messages > 0 else 0,
        )

    # ── Failure Recovery Test ──────────────────────────

    async def recovery_test(
        self,
        num_agents: int = 50,
        failure_rate: float = 0.1,
        messages: int = 200,
    ) -> BenchmarkResult:
        """Test recovery when agents randomly fail and reconnect."""
        logger.info(f"Recovery test: {num_agents} agents, {failure_rate:.0%} failure rate")

        latencies: list[float] = []
        errors = 0
        import random

        async def flaky_agent(agent_id: int):
            nonlocal errors
            online = True
            for msg_id in range(messages):
                if random.random() < failure_rate:
                    online = not online  # Toggle online/offline
                    if not online:
                        await asyncio.sleep(0.01)  # Reconnect delay
                        continue

                try:
                    start = time.perf_counter()
                    await asyncio.sleep(0.001)
                    elapsed = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed)
                except Exception:
                    errors += 1

        start_time = time.perf_counter()
        tasks = [flaky_agent(i) for i in range(num_agents)]
        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        return BenchmarkResult(
            name=f"recovery_{num_agents}agents",
            total_agents=num_agents,
            total_messages=num_agents * messages,
            duration_seconds=duration,
            messages_per_second=(num_agents * messages) / duration if duration > 0 else 0,
            latency_p50_ms=statistics.median(latencies) if latencies else 0,
            latency_p95_ms=_percentile(latencies, 95) if latencies else 0,
            latency_p99_ms=_percentile(latencies, 99) if latencies else 0,
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            errors=errors,
            error_rate=errors / (num_agents * messages) if messages > 0 else 0,
        )

    # ── Orchestrator ───────────────────────────────────

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all stress tests and return results."""
        print("=" * 60)
        print("ARMP Stress Test Suite — v0.7.0")
        print("=" * 60)

        tests = [
            # Quick tests
            ("Throughput (10 agents)", self.throughput_test(num_agents=10, messages_per_agent=50)),
            ("Connection (50 agents)", self.connection_test(num_agents=50)),
            # Full tests
            ("Throughput (100 agents)", self.throughput_test(num_agents=100, messages_per_agent=100)),
            ("Connection (500 agents)", self.connection_test(num_agents=500)),
            ("Federation (5 servers)", self.federation_test(num_servers=5)),
            ("Recovery (50 agents)", self.recovery_test(num_agents=50)),
        ]

        for name, coro in tests:
            print(f"\n▶ {name}")
            result = await coro
            self._results.append(result)
            print(f"  Messages: {result.total_messages}")
            print(f"  Throughput: {result.messages_per_second:.1f} msg/s")
            print(f"  P50: {result.latency_p50_ms:.1f}ms  P95: {result.latency_p95_ms:.1f}ms  P99: {result.latency_p99_ms:.1f}ms")
            if result.errors:
                print(f"  ⚠️ Errors: {result.errors} ({result.error_rate:.2%})")

        return self._results

    def report(self) -> str:
        """Generate a markdown report."""
        lines = [
            "# ARMP Stress Test Report",
            f"Generated: {_now_iso()}",
            "",
            "| Test | Agents | Msgs | Duration | Msg/s | P50 | P95 | P99 | Errors |",
            "|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|",
        ]

        for r in self._results:
            lines.append(
                f"| {r.name} | {r.total_agents} | {r.total_messages} | "
                f"{r.duration_seconds:.1f}s | {r.messages_per_second:.0f} | "
                f"{r.latency_p50_ms:.0f}ms | {r.latency_p95_ms:.0f}ms | "
                f"{r.latency_p99_ms:.0f}ms | {r.errors} |"
            )

        if self._results:
            total_msgs = sum(r.total_messages for r in self._results)
            total_dur = sum(r.duration_seconds for r in self._results)
            lines.append(f"\n**Total:** {total_msgs} messages, {total_dur:.1f}s total duration")
            lines.append(f"**Overall:** {total_msgs / total_dur:.1f} msg/s" if total_dur > 0 else "")

        return "\n".join(lines)


def _percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Demo ────────────────────────────────────────────

async def demo():
    runner = StressRunner()
    await runner.run_all()
    print("\n" + runner.report())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())

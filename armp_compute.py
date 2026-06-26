"""
ARMP Compute Sharing — Agent delegates computation with streaming results.

Phase 7: Enables Agent A to ask Agent B "run this computation for me"
and receive streaming results over Matrix/WebRTC. Supports:

- Synchronous: request → full result
- Streaming: request → progressive chunks
- GPU sharing: request → GPU-accelerated computation
- Cancellation: cancel a running computation
- Progress tracking: percent complete, ETA

Protocol: ARMP extension v0.7.0
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger("armp.compute")


class ComputeStatus(str, Enum):
    QUEUED = "queued"              # Waiting for capacity
    RUNNING = "running"            # Computation in progress
    STREAMING = "streaming"        # Streaming intermediate results
    COMPLETED = "completed"        # Done successfully
    FAILED = "failed"              # Computation failed
    CANCELLED = "cancelled"        # Cancelled by requester
    TIMED_OUT = "timed_out"        # Deadline exceeded


class ComputeType(str, Enum):
    INFERENCE = "inference"        # Model inference (LLM, diffusion, etc.)
    TRAINING = "training"          # Fine-tuning / training
    DATA_PROCESSING = "data_processing"  # ETL, aggregation, analysis
    RENDERING = "rendering"        # 3D rendering, video encoding
    SCIENTIFIC = "scientific"      # Simulation, numerical computation
    CUSTOM = "custom"              # Generic computation


@dataclass
class ComputeSpec:
    """Specification for a computation task."""
    compute_type: ComputeType = ComputeType.CUSTOM
    model: str = ""                           # Model name for inference
    framework: str = ""                        # pytorch, tensorflow, jax
    input_data: dict = field(default_factory=dict)   # Input parameters
    input_urls: list = field(default_factory=list)   # URLs to input data
    output_format: str = "json"               # json, bytes, stream
    gpu_required: bool = False
    gpu_min_memory_gb: float = 0.0
    cpu_cores: int = 1
    memory_gb: float = 1.0
    max_duration_seconds: int = 3600
    priority: int = 5                         # 1-10, higher = more urgent
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "compute_type": self.compute_type.value,
            "model": self.model,
            "framework": self.framework,
            "output_format": self.output_format,
            "gpu_required": self.gpu_required,
            "gpu_min_memory_gb": self.gpu_min_memory_gb,
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "max_duration_seconds": self.max_duration_seconds,
            "priority": self.priority,
            "tags": self.tags,
        }


@dataclass
class ComputeJob:
    """A running or completed computation job."""
    job_id: str
    requester_did: str
    provider_did: str
    spec: ComputeSpec
    status: ComputeStatus = ComputeStatus.QUEUED
    progress: float = 0.0                    # 0.0–1.0
    eta_seconds: float = 0.0
    result: Optional[dict] = None
    error: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    metrics: dict = field(default_factory=dict)  # CPU/GPU/memory usage

    def __post_init__(self):
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "requester_did": self.requester_did,
            "provider_did": self.provider_did,
            "spec": self.spec.to_dict(),
            "status": self.status.value,
            "progress": self.progress,
            "eta_seconds": self.eta_seconds,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metrics": self.metrics,
        }


class ComputeRegistry:
    """Registry of registered compute capabilities."""

    def __init__(self):
        self._capabilities: dict[str, list[ComputeSpec]] = {}  # did → specs
        self._availability: dict[str, dict] = {}  # did → {gpu_free, cpu_free, ...}

    def register(self, did: str, specs: list[ComputeSpec]):
        """Register compute capabilities for an agent."""
        self._capabilities[did] = specs

    def unregister(self, did: str):
        if did in self._capabilities:
            del self._capabilities[did]
        if did in self._availability:
            del self._availability[did]

    def update_availability(self, did: str, info: dict):
        """Update resource availability."""
        self._availability[did] = info

    def find_providers(self, spec: ComputeSpec) -> list[tuple[str, float]]:
        """Find providers matching a compute spec. Returns (did, score) pairs."""
        results = []
        for did, capabilities in self._capabilities.items():
            for cap in capabilities:
                if cap.compute_type != spec.compute_type:
                    continue
                if spec.gpu_required and not cap.gpu_required:
                    continue
                if spec.gpu_min_memory_gb > cap.gpu_min_memory_gb:
                    continue
                if spec.cpu_cores > cap.cpu_cores:
                    continue
                if spec.memory_gb > cap.memory_gb:
                    continue

                # Score based on resource match
                score = 1.0
                avail = self._availability.get(did, {})
                if avail.get("gpu_free", 0) < 1 and spec.gpu_required:
                    score *= 0.5
                score *= min(1.0, avail.get("cpu_free_pct", 1.0))
                results.append((did, score))

        return sorted(results, key=lambda x: -x[1])


class ComputeManager:
    """Manages compute jobs across the ARMP network."""

    def __init__(self, homeserver_url: str = ""):
        self.homeserver_url = homeserver_url
        self.registry = ComputeRegistry()
        self._jobs: dict[str, ComputeJob] = {}
        self._active_streams: dict[str, asyncio.Queue] = {}  # job_id → result chunks
        self._handlers: dict[str, Callable] = {}  # compute_type → handler fn
        self._max_concurrent = 10
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    # ── Handler Registration ──────────────────────────

    def register_handler(self, compute_type: ComputeType, handler: Callable):
        """Register a computation handler.

        Handler signature: async def handler(job: ComputeJob) -> AsyncIterator[dict]
        """
        self._handlers[compute_type.value] = handler

    # ── Job Lifecycle ─────────────────────────────────

    async def submit(self, requester_did: str, spec: ComputeSpec) -> ComputeJob:
        """Submit a computation job. Finds the best provider and queues it."""
        providers = self.registry.find_providers(spec)
        if not providers:
            raise ValueError(f"No provider found for {spec.compute_type.value}")

        provider_did, score = providers[0]

        job = ComputeJob(
            job_id=f"COMP-{uuid.uuid4().hex[:8].upper()}",
            requester_did=requester_did,
            provider_did=provider_did,
            spec=spec,
        )
        self._jobs[job.job_id] = job

        logger.info(f"Compute job submitted: {job.job_id} "
                     f"({spec.compute_type.value}) → {provider_did} (score={score:.2f})")

        # Start execution asynchronously
        asyncio.create_task(self._execute(job.job_id))
        return job

    async def submit_and_wait(self, requester_did: str, spec: ComputeSpec, timeout: float = 3600) -> ComputeJob:
        """Submit and block until completion."""
        job = await self.submit(requester_did, spec)
        deadline = time.time() + timeout

        while job.status in (ComputeStatus.QUEUED, ComputeStatus.RUNNING, ComputeStatus.STREAMING):
            if time.time() > deadline:
                await self.cancel(job.job_id, "timed out")
                break
            await asyncio.sleep(0.5)

        return job

    async def stream(self, requester_did: str, spec: ComputeSpec) -> AsyncIterator[dict]:
        """Submit and return an async iterator of result chunks."""
        job = await self.submit(requester_did, spec)
        queue: asyncio.Queue = asyncio.Queue()
        self._active_streams[job.job_id] = queue

        while True:
            chunk = await queue.get()
            if chunk is None:  # End of stream
                break
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            yield chunk

    async def cancel(self, job_id: str, reason: str = "") -> bool:
        """Cancel a running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status not in (ComputeStatus.QUEUED, ComputeStatus.RUNNING, ComputeStatus.STREAMING):
            return False

        job.status = ComputeStatus.CANCELLED
        job.completed_at = _now_iso()
        logger.info(f"Compute job cancelled: {job_id} — {reason}")
        return True

    async def get_progress(self, job_id: str) -> Optional[dict]:
        """Get current progress of a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "progress": job.progress,
            "eta_seconds": job.eta_seconds,
        }

    # ── Execution ─────────────────────────────────────

    async def _execute(self, job_id: str):
        """Execute a computation job."""
        job = self._jobs.get(job_id)
        if not job:
            return

        handler = self._handlers.get(job.spec.compute_type.value)
        if not handler:
            job.status = ComputeStatus.FAILED
            job.error = f"No handler for compute type: {job.spec.compute_type.value}"
            job.completed_at = _now_iso()
            return

        async with self._semaphore:
            job.status = ComputeStatus.RUNNING
            job.started_at = _now_iso()
            start_time = time.time()

            try:
                chunk_count = 0
                streaming = False

                async for chunk in handler(job):
                    chunk_count += 1
                    if not streaming:
                        streaming = True
                        job.status = ComputeStatus.STREAMING

                    # Send to stream queue
                    queue = self._active_streams.get(job.job_id)
                    if queue:
                        await queue.put(chunk)

                    # Update progress
                    if "progress" in chunk:
                        job.progress = chunk["progress"]
                    if "eta" in chunk:
                        job.eta_seconds = chunk["eta"]

                # Done streaming
                job.status = ComputeStatus.COMPLETED
                job.progress = 1.0
                job.metrics["chunks"] = chunk_count
                job.metrics["wall_time_seconds"] = time.time() - start_time

                # Signal end of stream
                queue = self._active_streams.get(job.job_id)
                if queue:
                    await queue.put(None)

            except asyncio.CancelledError:
                job.status = ComputeStatus.CANCELLED
            except Exception as e:
                job.status = ComputeStatus.FAILED
                job.error = str(e)
                logger.error(f"Compute job {job_id} failed: {e}")

            job.completed_at = _now_iso()

    # ── ARMP Message Integration ──────────────────────

    def format_compute_message(self, job: ComputeJob) -> dict:
        """Format a compute job as an ARMP matrix message."""
        return {
            "msgtype": "m.agent.compute",
            "body": f"Compute job {job.job_id}: {job.spec.compute_type.value}",
            "amp_metadata": {
                "version": "0.7.0",
                "compute_job": job.to_dict(),
            },
        }

    # ── Stats ─────────────────────────────────────────

    def stats(self) -> dict:
        jobs = list(self._jobs.values())
        completed = [j for j in jobs if j.status == ComputeStatus.COMPLETED]
        return {
            "total_jobs": len(jobs),
            "active": sum(1 for j in jobs if j.status in (ComputeStatus.QUEUED, ComputeStatus.RUNNING, ComputeStatus.STREAMING)),
            "completed": len(completed),
            "failed": sum(1 for j in jobs if j.status == ComputeStatus.FAILED),
            "cancelled": sum(1 for j in jobs if j.status == ComputeStatus.CANCELLED),
            "total_wall_time_seconds": sum(j.metrics.get("wall_time_seconds", 0) for j in completed),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Built-in Handlers ─────────────────────────────────

async def inference_handler(job: ComputeJob):
    """Example handler: model inference with progress."""
    total_steps = 10
    for i in range(total_steps):
        await asyncio.sleep(0.1)
        yield {
            "step": i + 1,
            "total": total_steps,
            "progress": (i + 1) / total_steps,
            "eta": (total_steps - i - 1) * 0.1,
            "intermediate": f"Step {i + 1}/{total_steps}",
        }
    yield {
        "result": {"output": "Inference complete", "tokens": 150},
        "progress": 1.0,
        "eta": 0,
    }


async def data_processing_handler(job: ComputeJob):
    """Example handler: data processing with streaming."""
    batches = ["batch_1", "batch_2", "batch_3"]
    for i, batch in enumerate(batches):
        await asyncio.sleep(0.05)
        yield {
            "batch": batch,
            "progress": (i + 1) / len(batches),
            "eta": (len(batches) - i - 1) * 0.05,
            "rows_processed": (i + 1) * 1000,
        }
    yield {
        "result": {"total_rows": 3000, "aggregations": {"mean": 42.0}},
        "progress": 1.0,
    }


# ── Demo ────────────────────────────────────────────

async def demo():
    """Demonstrate compute sharing."""
    print("🚀 ARMP Compute Sharing v0.7.0 — Demo\n")

    manager = ComputeManager()
    manager.registry.register("AGNT-B", [ComputeSpec(
        compute_type=ComputeType.INFERENCE,
        model="llama-3",
        framework="pytorch",
        gpu_required=True,
        gpu_min_memory_gb=16,
    )])
    manager.register_handler(ComputeType.INFERENCE, inference_handler)
    manager.register_handler(ComputeType.DATA_PROCESSING, data_processing_handler)

    # Submit a job
    spec = ComputeSpec(compute_type=ComputeType.INFERENCE, model="llama-3")
    job = await manager.submit("AGNT-A", spec)
    print(f"Job submitted: {job.job_id}")

    # Wait for completion
    while job.status not in (ComputeStatus.COMPLETED, ComputeStatus.FAILED):
        print(f"  Status: {job.status.value} ({job.progress:.0%})")
        await asyncio.sleep(0.2)

    print(f"\n  Final: {job.status.value}")
    print(f"  Time: {job.metrics.get('wall_time_seconds', 0):.1f}s")

    stats = manager.stats()
    print(f"\nStats: {stats['completed']} completed, {stats['failed']} failed")
    print("\n── Demo Complete ──\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())

# ARMP Compute Sharing — Specification v0.7.0

## 1. Overview

Compute Sharing enables ARMP agents to delegate computational work to other agents. Agent A sends a compute specification to Agent B, and Agent B executes the computation, returning streaming results.

## 2. Protocol Flow

```
Agent A (Requester)                    Agent B (Provider)
      │                                      │
      │── COMPUTE_REQUEST ──────────────────→│  "Run this model"
      │                                      │
      │←─ COMPUTE_ACCEPTED ─────────────────│  "I can do that"
      │                                      │
      │         [Computation runs]           │
      │←─ COMPUTE_STREAM (chunk 1) ─────────│  "Progress: 10%"
      │←─ COMPUTE_STREAM (chunk 2) ─────────│  "Progress: 50%"
      │←─ COMPUTE_STREAM (chunk N) ─────────│  "Result: {...}"
      │←─ COMPUTE_COMPLETE ─────────────────│  "Done"
```

## 3. Compute Types

| Type | Description | Examples |
|------|-------------|----------|
| `inference` | Model inference | LLM, diffusion, TTS |
| `training` | Fine-tuning | LoRA, RLHF |
| `data_processing` | ETL, aggregation | SQL queries, pandas |
| `rendering` | 3D, video | Blender, ffmpeg |
| `scientific` | Numerical | NumPy, simulation |
| `custom` | Generic | Arbitrary code |

## 4. Resource Specification

```json
{
  "compute_type": "inference",
  "model": "llama-3-70b",
  "framework": "pytorch",
  "gpu_required": true,
  "gpu_min_memory_gb": 48,
  "cpu_cores": 8,
  "memory_gb": 64,
  "max_duration_seconds": 3600,
  "priority": 7
}
```

## 5. Provider Discovery

Agents register compute capabilities on startup. The Compute Registry matches requests to providers based on:

1. Compute type match (exact)
2. GPU requirement match
3. Resource sufficiency (memory, cores)
4. Availability score (current load)
5. Priority-based queuing

## 6. Streaming

Results stream via `COMPUTE_STREAM` events with progress metadata:

```json
{
  "job_id": "COMP-77D7C912",
  "progress": 0.5,
  "eta_seconds": 5.0,
  "chunk": {"tokens": ["the", "cat", "sat"]}
}
```

## 7. Cancellation

A requester can cancel a running job via `COMPUTE_CANCEL`. The provider stops execution and cleans up resources.

## 8. Security

- All compute requests are authenticated via ARMP DID binding
- Providers can reject requests based on requester reputation
- GPU memory is isolated per job
- Timeouts enforced by the provider

## 9. Metrics

Each job records:
- Wall time
- GPU/CPU utilization
- Memory peak
- Chunk count
- Bytes processed

---

*Version 0.7.0. Apache 2.0.*

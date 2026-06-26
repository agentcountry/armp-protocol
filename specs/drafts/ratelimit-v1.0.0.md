# ARMP Rate Limiting Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

ARMP Rate Limiting protects homeservers and agents from abuse using token bucket and sliding window algorithms.

### 1.1 Design Goals

- **Fairness** — no single agent can monopolize resources
- **Graceful degradation** — clients receive clear feedback when limited
- **Multi-level** — limits at agent, room, server, IP, and global levels
- **Burst-friendly** — allow short bursts within capacity

---

## 2. Token Bucket Algorithm

### 2.1 Parameters

| Parameter | Default | Description |
|-----------|:--:|------------|
| `rate` | 10/s | Tokens added per second |
| `burst` | 100 | Maximum token capacity |

### 2.2 Operation

```
On each request:
  1. Refill: tokens += (now - last_refill) × rate, capped at burst
  2. If tokens >= 1: tokens -= 1, allow request
  3. If tokens < 1: reject with 429
```

---

## 3. Sliding Window Algorithm

### 3.1 Parameters

| Parameter | Default | Description |
|-----------|:--:|------------|
| `window_size` | 60s | Sliding window duration |
| `max_requests` | 100 | Maximum requests per window |
| `window_granularity` | 1s | Counter bucket size |

### 3.2 Operation

```
count = sum of counters in sliding window
if count >= max_requests: reject with 429
else: increment current bucket counter
```

---

## 4. Limit Scopes

Limits are applied at multiple levels simultaneously:

| Scope | Key | Example Limit |
|-------|-----|:--:|
| **Agent** | Agent DID | 10 msg/s per agent |
| **Room** | Room ID | 100 msg/s per room |
| **Server** | Federation server name | 1000 req/s per remote server |
| **IP** | Client IP address | 60 req/min per IP |
| **Global** | Server-wide | 10000 req/s total |

### 4.1 Scope Evaluation Order

All applicable scopes are checked. The request is rejected if ANY scope limit is exceeded.

---

## 5. Response Headers

When a limit is hit, the server returns:

```
HTTP 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1750000000
X-RateLimit-Scope: agent
```

---

## 6. Client Backoff

Clients MUST implement exponential backoff on 429 responses:

```
wait_time = min(base_delay × 2^attempts, max_delay)
```

| Parameter | Default |
|-----------|:--:|
| `base_delay` | 1 second |
| `max_delay` | 300 seconds (5 minutes) |
| `max_attempts` | 5 |

---

## 7. Reference Implementation

Python: `armp_ratelimit.py` — 358 lines
- `TokenBucket` dataclass with configurable rate and burst
- `SlidingWindow` class with granularity
- `RateLimiter` class evaluating all scopes
- `LimitScope` enum: AGENT, ROOM, SERVER, IP, GLOBAL

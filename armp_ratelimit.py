"""
ARMP Rate Limiting v0.5.0

Token bucket rate limiter for ARMP agents and rooms.
Protects against abuse while allowing burst traffic.

Features:
  - Per-agent rate limiting (token bucket algorithm)
  - Per-room rate limiting
  - Per-server federation rate limiting
  - Sliding window counters
  - Automatic backoff on limit hit
  - Rate limit headers for client feedback

Algorithm: Token bucket with configurable rate and burst.

Apache 2.0.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("armp-ratelimit")


# ── Types ────────────────────────────────────────────────

class LimitScope(str, Enum):
    AGENT = "agent"          # Per-agent limit
    ROOM = "room"            # Per-room limit
    SERVER = "server"        # Per-federation-server limit
    IP = "ip"                # Per-IP limit
    GLOBAL = "global"        # Server-wide limit


# ── Token Bucket ─────────────────────────────────────────

@dataclass
class TokenBucket:
    """A single token bucket rate limiter.

    Tokens refill at `rate` per second, up to `burst` maximum.
    """
    rate: float = 10.0        # Tokens added per second
    burst: float = 100.0      # Maximum tokens (burst capacity)
    tokens: float = 100.0     # Current token count
    last_refill: float = 0.0  # Unix timestamp of last refill

    def __post_init__(self):
        if not self.last_refill:
            self.last_refill = time.monotonic()

    def refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self, count: int = 1) -> bool:
        """Try to consume `count` tokens. Returns True if allowed."""
        self.refill()
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False

    @property
    def available(self) -> float:
        """Return currently available tokens."""
        self.refill()
        return self.tokens


# ── Sliding Window Counter ───────────────────────────────

@dataclass
class SlidingWindow:
    """Sliding window counter for rate limiting.

    Counts events within a moving time window.
    """
    window_seconds: float = 60.0  # Window size
    max_events: int = 100         # Max events per window

    def __init__(self, window_seconds: float = 60.0, max_events: int = 100):
        self.window_seconds = window_seconds
        self.max_events = max_events
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        """Check if an event is allowed. Returns True if under limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Remove old entries
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if len(self._timestamps) < self.max_events:
            self._timestamps.append(now)
            return True
        return False

    @property
    def current_count(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        return len([t for t in self._timestamps if t > cutoff])


# ── Rate Limiter ─────────────────────────────────────────

class RateLimiter:
    """
    Multi-level rate limiter for ARMP.

    Usage:
        rl = RateLimiter()
        rl.set_limit("agent-alpha", rate=10, burst=100)  # 10 msg/s, burst 100
        rl.set_room_limit("room-001", rate=50, burst=500)

        if rl.allow("agent-alpha"):
            process_message()
        else:
            return rate_limit_error()
    """

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}       # key → bucket
        self._windows: dict[str, SlidingWindow] = {}     # key → sliding window
        self._hit_counters: dict[str, int] = {}           # key → consecutive hits
        self._blocked_until: dict[str, float] = {}        # key → unblock time

    # ── Configuration ────────────────────────────────

    def set_limit(self, key: str, rate: float, burst: float = None):
        """Set token bucket limit for a key."""
        burst = burst or rate * 10  # Default burst = 10 seconds worth
        self._buckets[key] = TokenBucket(rate=rate, burst=burst)

    def set_window_limit(self, key: str, window_seconds: float, max_events: int):
        """Set sliding window limit for a key."""
        self._windows[key] = SlidingWindow(window_seconds, max_events)

    def set_defaults(self, agent_rate: float = 10.0, agent_burst: float = 100.0,
                     room_rate: float = 100.0, room_burst: float = 1000.0,
                     global_rate: float = 1000.0, global_burst: float = 10000.0):
        """Set default rate limits for agents, rooms, and global."""
        self.set_limit("__global__", global_rate, global_burst)
        self.set_limit("__agent_default__", agent_rate, agent_burst)
        self.set_limit("__room_default__", room_rate, room_burst)

    def set_agent_limit(self, agent_did: str, rate: float, burst: float = None):
        """Set rate limit for a specific agent."""
        self.set_limit(f"agent:{agent_did}", rate, burst)

    def set_room_limit(self, room_id: str, rate: float, burst: float = None):
        """Set rate limit for a specific room."""
        self.set_limit(f"room:{room_id}", rate, burst)

    def set_federation_limit(self, server_name: str, rate: float, burst: float = None):
        """Set rate limit for a federated server."""
        self.set_limit(f"federation:{server_name}", rate, burst)

    # ── Checking ─────────────────────────────────────

    def allow(self, agent_did: str = "", room_id: str = "",
              server_name: str = "", count: int = 1) -> bool:
        """Check if an operation is allowed across all applicable limits.

        Checks in order: global → agent → room → federation.
        """
        # Check if blocked
        for prefix, key in [("agent", agent_did), ("room", room_id), ("federation", server_name)]:
            block_key = f"{prefix}:{key}" if key else ""
            if block_key in self._blocked_until:
                if time.monotonic() < self._blocked_until[block_key]:
                    return False
                del self._blocked_until[block_key]

        # Check global
        if not self._check_bucket("__global__", count):
            self._record_hit("__global__")
            return False

        # Check agent
        if agent_did:
            agent_key = f"agent:{agent_did}"
            if not self._check_bucket(agent_key, count, fallback_key="__agent_default__"):
                self._record_hit(agent_key)
                return False

        # Check room
        if room_id:
            room_key = f"room:{room_id}"
            if not self._check_bucket(room_key, count, fallback_key="__room_default__"):
                self._record_hit(room_key)
                return False

        # Check federation
        if server_name:
            fed_key = f"federation:{server_name}"
            if not self._check_bucket(fed_key, count):
                self._record_hit(fed_key)
                return False

        return True

    def _check_bucket(self, key: str, count: int = 1,
                       fallback_key: str = "") -> bool:
        """Check a specific token bucket."""
        bucket = self._buckets.get(key)
        if not bucket and fallback_key:
            bucket = self._buckets.get(fallback_key)
        if not bucket:
            return True  # No limit configured
        return bucket.consume(count)

    def _record_hit(self, key: str):
        """Record a rate limit hit and apply backoff if needed."""
        self._hit_counters[key] = self._hit_counters.get(key, 0) + 1
        hits = self._hit_counters[key]

        if hits >= 10:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s (max)
            backoff = min(32, 2 ** (hits - 10))
            self._blocked_until[key] = time.monotonic() + backoff
            logger.warning(f"Rate limit hit #{hits}: {key} blocked for {backoff}s")

    # ── Status ───────────────────────────────────────

    def status(self, key: str = "__global__") -> dict:
        """Get rate limit status for a key."""
        bucket = self._buckets.get(key)
        if not bucket:
            return {"key": key, "status": "unlimited"}

        return {
            "key": key,
            "rate": bucket.rate,
            "burst": bucket.burst,
            "available": round(bucket.available, 1),
            "usage_pct": round((1 - bucket.available / bucket.burst) * 100, 1),
            "hits": self._hit_counters.get(key, 0),
            "blocked": key in self._blocked_until,
        }

    def all_status(self) -> list[dict]:
        """Get status for all rate-limited keys."""
        return [self.status(key) for key in sorted(self._buckets.keys())]

    def reset(self, key: str = ""):
        """Reset rate limits for a specific key, or all if empty."""
        if key:
            if key in self._buckets:
                bucket = self._buckets[key]
                bucket.tokens = bucket.burst
            self._hit_counters.pop(key, None)
            self._blocked_until.pop(key, None)
        else:
            for bucket in self._buckets.values():
                bucket.tokens = bucket.burst
            self._hit_counters.clear()
            self._blocked_until.clear()


# ── Rate Limit Middleware ────────────────────────────────

class RateLimitMiddleware:
    """Middleware-style wrapper for ARMP operations.

    Usage:
        rl = RateLimitMiddleware(rate_limiter)
        @rl.throttle
        async def handle_message(agent_did, room_id, content):
            ...
    """

    def __init__(self, rate_limiter: RateLimiter):
        self.rl = rate_limiter

    def throttle(self, func):
        """Decorator that rate-limits a function call."""
        async def wrapper(*args, **kwargs):
            # Extract agent_did and room_id from args/kwargs
            agent_did = kwargs.get("agent_did", args[0] if args else "")
            room_id = kwargs.get("room_id", "")

            if not self.rl.allow(agent_did=agent_did, room_id=room_id):
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {agent_did or 'unknown'}"
                )
            return await func(*args, **kwargs)
        return wrapper


class RateLimitExceededError(Exception):
    """Raised when a rate limit is exceeded."""
    pass


# ── Demo ────────────────────────────────────────────

def demo():
    print("🚀 ARMP Rate Limiting v0.5.0 — Demo\n")

    rl = RateLimiter()
    rl.set_defaults(
        agent_rate=10, agent_burst=50,
        room_rate=50, room_burst=200,
    )
    rl.set_agent_limit("agent-alpha", rate=5, burst=25)

    print("── Token Bucket (agent-alpha: 5/s, burst=25) ──")
    # Burst consume 30
    allowed = 0
    for i in range(30):
        if rl.allow(agent_did="agent-alpha"):
            allowed += 1
    print(f"  Burst 30 → allowed {allowed} (rate=5/s, burst=25)")

    status = rl.status("agent:agent-alpha")
    print(f"  Available: {status['available']} / {status['burst']}")
    print(f"  Usage: {status['usage_pct']}%")

    # Simulate sustained rate limit hits
    print("\n── Sustained Overload ──")
    rl.reset()
    hits = 0
    for i in range(100):
        if not rl.allow(agent_did="agent-alpha"):
            hits += 1
    print(f"  Out of 100 attempts: {hits} blocked")

    # Sliding window
    print("\n── Sliding Window (60s, max=10) ──")
    window = SlidingWindow(window_seconds=60, max_events=10)
    for i in range(15):
        window.allow()
    print(f"  Attempted 15, current count: {window.current_count}")

    # Federation limits
    rl.set_federation_limit("armp-node2.org", rate=20, burst=200)
    rl.set_federation_limit("armp-node3.org", rate=20, burst=200)
    print(f"\n── Federation Limits ──")
    for server in ["armp-node2.org", "armp-node3.org", "matrix.org"]:
        status = rl.status(f"federation:{server}")
        limited = "limited" if status.get("rate") else "unlimited"
        print(f"  {server}: {limited}")

    print("\n── Rate Limit Demo Complete ──\n")


if __name__ == "__main__":
    demo()

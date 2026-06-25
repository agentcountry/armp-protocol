"""
ARMP Reputation System v0.5.0

Decentralized agent reputation based on task history and peer reviews.
Enables agents to build trust through verifiable performance.

Scoring model:
  - Task completion rate (40%)
  - Task quality (peer ratings, 30%)
  - Response time (15%)
  - Consistency (15%)

Features:
  - Task-based reputation scoring
  - Peer review collection
  - Reputation tiers (Bronze → Silver → Gold → Platinum)
  - Historical trend analysis
  - Leaderboard

Apache 2.0.
"""

import hashlib
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("armp-reputation")


# ── Reputation Tier ──────────────────────────────────────

class ReputationTier(str, Enum):
    NEWCOMER = "newcomer"       # < 0.3
    BRONZE = "bronze"           # 0.3-0.5
    SILVER = "silver"           # 0.5-0.7
    GOLD = "gold"               # 0.7-0.9
    PLATINUM = "platinum"       # 0.9-1.0


def tier_from_score(score: float) -> ReputationTier:
    if score >= 0.9: return ReputationTier.PLATINUM
    if score >= 0.7: return ReputationTier.GOLD
    if score >= 0.5: return ReputationTier.SILVER
    if score >= 0.3: return ReputationTier.BRONZE
    return ReputationTier.NEWCOMER


# ── Data Models ──────────────────────────────────────────

@dataclass
class TaskRecord:
    """A completed or failed task, used for reputation scoring."""
    task_id: str
    agent_did: str
    client_did: str
    status: str  # COMPLETED, FAILED
    response_time_ms: int = 0
    created_at: str = ""
    completed_at: str = ""


@dataclass
class PeerReview:
    """A review submitted by a peer after task completion."""
    review_id: str = ""
    reviewer_did: str = ""
    subject_did: str = ""
    task_id: str = ""
    rating: float = 0.5  # 0.0-1.0
    categories: dict = field(default_factory=dict)  # {quality, speed, communication}
    comment: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.review_id:
            self.review_id = f"rev-{hashlib.sha256(f'{self.reviewer_did}{self.task_id}{time.time()}'.encode()).hexdigest()[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ── Reputation Engine ────────────────────────────────────

class ReputationEngine:
    """
    Calculates and stores agent reputation scores.

    Usage:
        engine = ReputationEngine()
        engine.record_task_completion("task-001", "agent-alpha", 1200)
        engine.add_review(PeerReview(reviewer_did="...", subject_did="agent-alpha", rating=0.95))
        score = engine.get_score("agent-alpha")
    """

    def __init__(self):
        self._tasks: dict[str, list[TaskRecord]] = {}  # agent_did → tasks
        self._reviews: dict[str, list[PeerReview]] = {}  # subject_did → reviews
        self._scores: dict[str, float] = {}  # cached scores

    def record_task_completion(self, task_id: str, agent_did: str,
                                client_did: str = "", status: str = "COMPLETED",
                                response_time_ms: int = 0):
        """Record a completed or failed task."""
        record = TaskRecord(
            task_id=task_id,
            agent_did=agent_did,
            client_did=client_did,
            status=status,
            response_time_ms=response_time_ms,
            created_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        if agent_did not in self._tasks:
            self._tasks[agent_did] = []
        self._tasks[agent_did].append(record)

        # Invalidate cached score
        self._scores.pop(agent_did, None)
        logger.info(f"Task {task_id}: {agent_did} → {status}")

    def add_review(self, review: PeerReview):
        """Add a peer review after task completion."""
        if review.subject_did not in self._reviews:
            self._reviews[review.subject_did] = []
        self._reviews[review.subject_did].append(review)

        self._scores.pop(review.subject_did, None)
        logger.info(f"Review: {review.subject_did} rated {review.rating:.2f} by {review.reviewer_did}")

    def get_score(self, agent_did: str) -> float:
        """Calculate the reputation score for an agent."""
        if agent_did in self._scores:
            return self._scores[agent_did]

        tasks = self._tasks.get(agent_did, [])
        reviews = self._reviews.get(agent_did, [])

        score = 0.0
        weights = 0.0

        # 1. Completion rate (40%)
        if tasks:
            completed = [t for t in tasks if t.status == "COMPLETED"]
            completion_rate = len(completed) / len(tasks)
            score += completion_rate * 0.4
        weights += 0.4

        # 2. Peer ratings (30%)
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
            score += avg_rating * 0.3
        else:
            score += 0.5 * 0.3  # Neutral default
        weights += 0.3

        # 3. Response time (15%)
        if tasks:
            times = [t.response_time_ms for t in tasks if t.response_time_ms > 0]
            if times:
                avg_time = statistics.mean(times)
                # Normalize: < 5s = 1.0, > 60s = 0.0
                time_score = max(0.0, min(1.0, 1.0 - (avg_time - 5000) / 55000))
                score += time_score * 0.15
            else:
                score += 0.5 * 0.15
        weights += 0.15

        # 4. Consistency (15%) — variance of ratings
        if reviews and len(reviews) >= 3:
            ratings_list = [r.rating for r in reviews]
            variance = statistics.variance(ratings_list) if len(ratings_list) > 1 else 0
            consistency_score = max(0.0, 1.0 - variance * 20)  # Low variance = high consistency
            score += consistency_score * 0.15
        else:
            score += 0.5 * 0.15
        weights += 0.15

        result = min(1.0, score) if weights > 0 else 0.5
        self._scores[agent_did] = result
        return result

    def get_tier(self, agent_did: str) -> ReputationTier:
        """Get the reputation tier for an agent."""
        return tier_from_score(self.get_score(agent_did))

    def get_stats(self, agent_did: str) -> dict:
        """Get detailed reputation statistics."""
        tasks = self._tasks.get(agent_did, [])
        reviews = self._reviews.get(agent_did, [])
        completed = [t for t in tasks if t.status == "COMPLETED"]

        return {
            "did": agent_did,
            "score": self.get_score(agent_did),
            "tier": self.get_tier(agent_did).value,
            "tasks_total": len(tasks),
            "tasks_completed": len(completed),
            "tasks_failed": len(tasks) - len(completed),
            "completion_rate": len(completed) / len(tasks) if tasks else 0,
            "reviews_count": len(reviews),
            "avg_rating": (sum(r.rating for r in reviews) / len(reviews)) if reviews else 0,
            "avg_response_ms": (statistics.mean([t.response_time_ms for t in tasks if t.response_time_ms > 0])
                               if tasks else 0),
        }

    def get_leaderboard(self, limit: int = 10) -> list[dict]:
        """Get top N agents by reputation score."""
        all_agents = set(self._tasks.keys()) | set(self._reviews.keys())
        scored = [(did, self.get_score(did)) for did in all_agents]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "rank": i + 1,
                "did": did,
                "score": round(score, 3),
                "tier": tier_from_score(score).value,
                "tasks": len(self._tasks.get(did, [])),
                "reviews": len(self._reviews.get(did, [])),
            }
            for i, (did, score) in enumerate(scored[:limit])
        ]

    def get_trend(self, agent_did: str, window: int = 10) -> dict:
        """Get score trend over recent tasks."""
        tasks = self._tasks.get(agent_did, [])[-window:]
        if not tasks:
            return {"direction": "stable", "change": 0.0}

        completed = [t for t in tasks if t.status == "COMPLETED"]
        trend = len(completed) / len(tasks)

        if trend >= 0.9:
            direction = "rising"
        elif trend <= 0.5:
            direction = "falling"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "recent_completion_rate": trend,
            "tasks_analyzed": len(tasks),
        }


# ── Reputation-Based Access Control ──────────────────────

class ReputationGate:
    """
    Gates access based on agent reputation.

    Usage:
        gate = ReputationGate(engine)
        if gate.allow_task(agent_did, min_tier=ReputationTier.SILVER):
            await process_task()
    """

    def __init__(self, engine: ReputationEngine):
        self.engine = engine

    def allow_task(self, agent_did: str, min_tier: ReputationTier = ReputationTier.BRONZE,
                    min_score: float = 0.0) -> bool:
        """Check if an agent is reputable enough to accept a task."""
        tier = self.engine.get_tier(agent_did)
        score = self.engine.get_score(agent_did)

        tier_rank = {ReputationTier.NEWCOMER: 0, ReputationTier.BRONZE: 1,
                      ReputationTier.SILVER: 2, ReputationTier.GOLD: 3,
                      ReputationTier.PLATINUM: 4}

        if tier_rank.get(tier, 0) < tier_rank.get(min_tier, 0):
            return False
        if score < min_score:
            return False
        return True

    def require_premium(self, agent_did: str) -> bool:
        """Check if an agent qualifies for premium/high-value tasks."""
        return self.allow_task(agent_did, ReputationTier.GOLD, 0.8)


# ── Demo ────────────────────────────────────────────

def demo():
    print("🚀 ARMP Reputation System v0.5.0 — Demo\n")

    engine = ReputationEngine()
    gate = ReputationGate(engine)

    # Agent Alpha: strong performer
    for i in range(25):
        engine.record_task_completion(
            f"task-{i:03d}", "agent-alpha",
            status="COMPLETED" if i < 23 else "FAILED",
            response_time_ms=1200 + (i * 50),
        )

    # Agent Beta: inconsistent
    for i in range(15):
        engine.record_task_completion(
            f"task-b-{i:03d}", "agent-beta",
            status="COMPLETED" if i % 3 != 0 else "FAILED",
            response_time_ms=5000 + (i * 200),
        )

    # Add peer reviews
    for i in range(8):
        engine.add_review(PeerReview(
            reviewer_did="agent-beta",
            subject_did="agent-alpha",
            task_id=f"task-{i:03d}",
            rating=0.85 + (i * 0.02),
            categories={"quality": 0.9, "speed": 0.8, "communication": 0.85},
        ))

    for i in range(4):
        engine.add_review(PeerReview(
            reviewer_did="agent-alpha",
            subject_did="agent-beta",
            task_id=f"task-b-{i:03d}",
            rating=0.4 + (i * 0.1),
        ))

    print("── Reputation Scores ──")
    for did in ["agent-alpha", "agent-beta"]:
        stats = engine.get_stats(did)
        print(f"  {did}: score={stats['score']:.3f} ({stats['tier']})")
        print(f"    Tasks: {stats['tasks_completed']}/{stats['tasks_total']} completed "
              f"({stats['completion_rate']:.0%})")
        print(f"    Reviews: {stats['reviews_count']}, avg={stats['avg_rating']:.2f}")
        trend = engine.get_trend(did)
        print(f"    Trend: {trend['direction']} ({trend['recent_completion_rate']:.0%})")

    print("\n── Leaderboard ──")
    for entry in engine.get_leaderboard(5):
        print(f"  #{entry['rank']} {entry['did']}: {entry['score']:.3f} ({entry['tier']}) — "
              f"{entry['tasks']} tasks, {entry['reviews']} reviews")

    print("\n── Access Control ──")
    print(f"  Alpha for SILVER task: {gate.allow_task('agent-alpha', ReputationTier.SILVER)}")
    print(f"  Alpha for GOLD task:   {gate.allow_task('agent-alpha', ReputationTier.GOLD)}")
    print(f"  Alpha premium:         {gate.require_premium('agent-alpha')}")
    print(f"  Beta  for SILVER task: {gate.allow_task('agent-beta', ReputationTier.SILVER)}")
    print(f"  Beta  premium:         {gate.require_premium('agent-beta')}")

    print("\n── Reputation Demo Complete ──\n")


if __name__ == "__main__":
    demo()

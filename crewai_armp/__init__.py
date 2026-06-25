"""
CrewAI ARMP Integration v0.4.0

Enables CrewAI multi-agent teams to use ARMP as their communication transport.
CrewAI agents delegate tasks and share results via ARMP Matrix rooms.

Usage:
    from crewai_armp import ARMPCrew, ARMPAgent

    crew = ARMPCrew(
        agents=[agent_alpha, agent_beta],
        armp_homeserver="https://armp-group.org",
    )
    result = await crew.kickoff(task="Analyze Q3 churn data")
Apache 2.0.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("crewai-armp")


# ── CrewAI ARMP Agent Wrapper ────────────────────────────

@dataclass
class ARMPCrewAgent:
    """
    A CrewAI-compatible agent that communicates via ARMP.

    Maps CrewAI agent concepts (role, goal, backstory) to ARMP Agent Cards.
    """

    role: str
    goal: str
    backstory: str = ""
    armp_agent: Any = None  # ARMP Agent instance
    armp_did: str = ""
    armp_username: str = ""
    armp_homeserver: str = ""
    tools: list = field(default_factory=list)
    verbose: bool = False

    async def start(self):
        """Start the ARMP agent and register capabilities."""
        if self.armp_agent:
            await self.armp_agent.set_capability(self.role, self.goal)
            await self.armp_agent.set_capability("crewai", "CrewAI multi-agent framework")
            if self.verbose:
                logger.info(f"CrewAI Agent '{self.role}': {self.goal}")

    async def execute_task(self, task_description: str, context: dict = None) -> dict:
        """Execute a CrewAI task via ARMP.

        The agent receives the task, processes it, and returns the result.
        """
        if not self.armp_agent:
            return {"error": "ARMP agent not connected", "role": self.role}

        task = await self.armp_agent.create_task(
            assignee_did=self.armp_agent.did,
            spec={
                "description": task_description,
                "context": context or {},
                "role": self.role,
                "goal": self.goal,
            },
        )

        # In production: the agent's LLM would process this task
        # For the integration, we return the task as pending
        return {
            "task_id": task.task_id,
            "status": task.status,
            "role": self.role,
            "message": f"Task assigned to {self.role}: {task_description[:100]}",
        }


# ── ARMP Crew ────────────────────────────────────────────

class ARMPCrew:
    """
    A CrewAI-like crew that orchestrates multiple ARMP agents.

    Agents communicate via ARMP Matrix rooms and negotiate capabilities.
    """

    def __init__(
        self,
        agents: list[ARMPCrewAgent],
        armp_homeserver: str = "https://armp-group.org",
        verbose: bool = False,
    ):
        self.agents = agents
        self.armp_homeserver = armp_homeserver
        self.verbose = verbose
        self._room_id: Optional[str] = None

    async def kickoff(self, task: str, context: dict = None) -> dict:
        """
        Kick off a CrewAI workflow:

        1. All agents connect and negotiate capabilities
        2. Task is smart-routed to the best agent
        3. Results are collected and returned
        """
        context = context or {}
        results = {
            "task": task,
            "agents": [a.role for a in self.agents],
            "phases": {},
        }

        # Phase 1: Connect all agents
        for agent in self.agents:
            await agent.start()

        # Phase 2: Create shared room
        if self.agents and self.agents[0].armp_agent:
            leader = self.agents[0].armp_agent
            member_ids = []
            for a in self.agents:
                if a.armp_agent and a.armp_agent.user_id:
                    member_ids.append(a.armp_agent.user_id)

            self._room_id = await leader.create_room(
                name=f"Crew: {self.agents[0].role}'s Team",
                members=member_ids,
                topic=f"ARMP CrewAI Team — {task[:100]}",
            )
            results["phases"]["connect"] = {"room_id": self._room_id, "members": member_ids}

        # Phase 3: Negotiate capabilities
        negotiations = {}
        for i, agent in enumerate(self.agents):
            if not agent.armp_agent:
                continue
            for j, peer in enumerate(self.agents):
                if i >= j or not peer.armp_agent:
                    continue
                try:
                    result = await agent.armp_agent.negotiate(peer.armp_agent.user_id)
                    negotiations[f"{agent.role}↔{peer.role}"] = {
                        "mutual": result.mutual_capabilities,
                        "matched": result.matched,
                    }
                except Exception as e:
                    negotiations[f"{agent.role}↔{peer.role}"] = {"error": str(e)}
        results["phases"]["negotiate"] = negotiations

        # Phase 4: Smart-route task to best agent
        if self.agents and self.agents[0].armp_agent:
            leader = self.agents[0].armp_agent
            best_card, best_id, score = await leader.route_task(
                {
                    "description": task,
                    "capabilities_required": context.get("capabilities_required", []),
                    "capabilities_preferred": context.get("capabilities_preferred", []),
                }
            )
            results["phases"]["route"] = {
                "best_agent": best_card.name if best_card else "none",
                "score": score,
                "user_id": best_id,
            }

        # Phase 5: Execute on each agent
        executions = {}
        for agent in self.agents:
            exec_result = await agent.execute_task(task, context)
            executions[agent.role] = exec_result
        results["phases"]["execute"] = executions

        results["status"] = "completed"
        return results


# ── Demo ────────────────────────────────────────────

async def demo():
    """Demo CrewAI ARMP integration without requiring CrewAI installed."""

    print("🚀 CrewAI ARMP Integration v0.4.0 — Demo\n")

    print("  ARMPCrewAgent: Wraps an ARMP agent as a CrewAI-compatible agent")
    print("  → agent = ARMPCrewAgent(role='Data Analyst', goal='Analyze churn', armp_agent=agent)")
    print()
    print("  ARMPCrew: Orchestrates multi-agent teams over ARMP")
    print("  → crew = ARMPCrew(agents=[analyst, reporter])")
    print("  → result = await crew.kickoff(task='Analyze Q3 churn')")
    print()
    print("  Workflow:")
    print("    1. All agents connect → ARMP Matrix")
    print("    2. Shared room created for collaboration")
    print("    3. Capabilities negotiated between all pairs")
    print("    4. Task smart-routed to best agent")
    print("    5. Each agent executes its part")
    print()
    print("── Integration Demo Complete ──\n")


if __name__ == "__main__":
    asyncio.run(demo())

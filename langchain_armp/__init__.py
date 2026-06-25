"""
LangChain ARMP Plugin v0.4.0

Integrates ARMP real-time agent communication into LangChain.
LangChain agents can use ARMP to:
  - Discover peer agents' capabilities
  - Delegate tasks to other agents via ARMP
  - Receive real-time progress updates
  - Collaborate in multi-agent rooms

Install: pip install langchain-armp
Usage: from langchain_armp import ARMPTool, ARMPChatModel
Apache 2.0.
"""

import asyncio
import json
import logging
from typing import Any, Optional

try:
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import CallbackManagerForToolRun
except ImportError:
    BaseTool = object  # type: ignore
    CallbackManagerForToolRun = None  # type: ignore

logger = logging.getLogger("langchain-armp")


# ── ARMP Tool ────────────────────────────────────────────

class ARMPTool(BaseTool):
    """LangChain Tool that delegates work to an ARMP agent.

    Examples:
        tool = ARMPTool(
            name="data_analysis_agent",
            description="Send data analysis tasks to the ARMP data agent",
            armp_agent=my_armp_agent,
            target_did="AGNT2F2026070116Z3R1M8K5Q9",
        )
    """

    name: str = "armp_agent"
    description: str = "Delegate a task to an ARMP agent for processing."
    armp_agent: Any = None  # ARMP Agent instance
    target_did: str = ""
    target_user_id: str = ""

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Synchronous run (calls async)."""
        return asyncio.run(self._arun(query, run_manager))

    async def _arun(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Async: send a task to the ARMP agent."""
        if not self.armp_agent:
            return "Error: ARMP agent not connected"

        # Create task
        task = await self.armp_agent.create_task(
            assignee_did=self.target_did,
            spec={
                "description": query[:200],
                "capabilities_required": [self.name.split("_")[0]],
                "query": query,
            },
            assignee_user_id=self.target_user_id,
        )

        # Wait for result (simplified — in production, use callbacks)
        for _ in range(60):  # Wait up to 60 seconds
            await asyncio.sleep(1)
            updated = self.armp_agent.get_task(task.task_id)
            if updated and updated.status in ("COMPLETED", "FAILED"):
                return json.dumps(updated.result or {"status": updated.status, "progress": updated.progress})

        return json.dumps({"status": "IN_PROGRESS", "task_id": task.task_id, "message": "Task is still running"})


# ── ARMP Chat Model (Agent-as-Model) ─────────────────────

class ARMPAgentChatModel:
    """
    Wrap an ARMP agent as if it were a LangChain chat model.

    Instead of calling an LLM API, this "model" forwards prompts
    to an ARMP agent and returns the agent's response.

    Usage:
        model = ARMPAgentChatModel(
            armp_agent=my_agent,
            target_did="AGNT2F2026070116Z3R1M8K5Q9",
        )
        result = await model.ainvoke("Analyze this dataset...")
    """

    def __init__(self, armp_agent: Any, target_did: str = "", target_user_id: str = ""):
        self.armp_agent = armp_agent
        self.target_did = target_did
        self.target_user_id = target_user_id
        self._message_history: list = []

    async def ainvoke(self, prompt: str) -> str:
        """Send a prompt to the ARMP agent and get the response."""
        if not self.armp_agent:
            raise RuntimeError("ARMP agent not connected")

        # Discover best agent via smart routing if no target
        user_id = self.target_user_id
        if not user_id:
            card, user_id, score = await self.armp_agent.route_task(
                {"description": prompt}
            )
            if not user_id:
                return "No suitable agent found for this task"

        # Negotiate capabilities
        result = await self.armp_agent.negotiate(user_id)

        # Send message
        event_id = await self.armp_agent.send_message(
            user_id,
            prompt,
            armp_meta={
                "capabilities_used": result.mutual_capabilities,
                "source": "langchain",
            },
        )

        # Wait for response (simplified — poll for reply)
        for _ in range(30):
            await asyncio.sleep(1)
            history = await self.armp_agent.get_history(
                room_id=await self.armp_agent._ensure_dm(user_id), limit=5
            )
            for msg in reversed(history):
                if msg.sender == user_id and msg.event_id > event_id:
                    return msg.body

        return "Agent did not respond within 30 seconds"

    def invoke(self, prompt: str) -> str:
        """Synchronous invoke."""
        return asyncio.run(self.ainvoke(prompt))


# ── ARMP Multi-Agent Chain ───────────────────────────────

class ARMPAgentChain:
    """
    Chain that orchestrates multiple ARMP agents working together.

    Usage:
        chain = ARMPAgentChain(
            agents=[agent_a, agent_b],
            task="Analyze churn data and generate report"
        )
        result = await chain.run()
    """

    def __init__(self, agents: list, task: str = ""):
        self.agents = agents
        self.task = task

    async def run(self) -> dict:
        """Execute the task across all agents."""
        results = {}

        # Start all agents
        for agent in self.agents:
            if not agent.is_online:
                await agent.start()

        # Discover each other
        for i, agent in enumerate(self.agents):
            for j, peer in enumerate(self.agents):
                if i >= j:
                    continue
                try:
                    result = await agent.negotiate(peer.user_id)
                    results[f"negotiate_{i}_{j}"] = {
                        "mutual": result.mutual_capabilities,
                        "missing": result.missing_capabilities,
                    }
                except Exception as e:
                    results[f"negotiate_{i}_{j}"] = {"error": str(e)}

        # Delegate task to first agent, let it route
        if self.agents and self.task:
            task = await self.agents[0].create_task(
                assignee_did=self.agents[-1].did,
                spec={"description": self.task},
                assignee_user_id=self.agents[-1].user_id,
            )
            results["task"] = {"task_id": task.task_id, "status": task.status}

        return results


# ── Demo ────────────────────────────────────────────

async def demo():
    """Demo the LangChain ARMP plugin without requiring LangChain installed."""

    print("🚀 LangChain ARMP Plugin v0.4.0 — Demo\n")

    print("  ARMPTool: Wrap an ARMP agent as a LangChain tool")
    print("  → tool = ARMPTool(name='data_analyst', armp_agent=agent, target_did='...')")
    print("  → result = tool.run('Analyze churn data')")
    print()
    print("  ARMPAgentChatModel: Use ARMP agent as if it were an LLM")
    print("  → model = ARMPAgentChatModel(armp_agent=agent)")
    print("  → result = await model.ainvoke('What is the churn rate?')")
    print()
    print("  ARMPAgentChain: Orchestrate multi-agent workflows")
    print("  → chain = ARMPAgentChain(agents=[agent_a, agent_b], task='...')")
    print("  → results = await chain.run()")
    print()
    print("── Plugin Demo Complete ──\n")


if __name__ == "__main__":
    asyncio.run(demo())

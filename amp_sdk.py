"""
ARMP Python SDK v0.1.0

Agent Real-time Message Protocol — Python client library.
Built on matrix-nio. Apache 2.0.

Quickstart:
    from amp_sdk import Agent

    agent = Agent(
        did="AGNT8A2026070114K7P2M9X4R6",
        homeserver="https://matrix.example.org",
        access_token="$TOKEN"
    )
    await agent.start()
    await agent.send_message("AGNT8B...", "Hello from ARMP!")
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid
import json
import logging

logger = logging.getLogger("amp-sdk")


# ── Data Models ────────────────────────────────────────────

@dataclass
class AgentCard:
    """An agent's public identity and capability card."""
    did: str
    name: str
    matrix_id: str
    description: str = ""
    capabilities: list = field(default_factory=list)
    endpoints: dict = field(default_factory=dict)
    version: str = "0.1.0"


@dataclass
class Message:
    """An ARMP message."""
    message_id: str
    sender_did: str
    body: str
    msgtype: str = "m.text"
    task_id: Optional[str] = None
    priority: str = "normal"
    ttl_seconds: int = 3600


@dataclass
class Task:
    """A task assigned between agents."""
    task_id: str
    sender_did: str
    assignee_did: str
    status: str = "CREATED"
    spec: dict = field(default_factory=dict)
    result: Optional[dict] = None


# ── Agent Class ────────────────────────────────────────────

class Agent:
    """
    An ARMP-compliant AI agent.

    Parameters
    ----------
    did : str
        Agent's DID (e.g., AGNT8A2026070114K7P2M9X4R6)
    homeserver : str
        Matrix homeserver URL (e.g., https://matrix.armp-group.org)
    access_token : str
        Matrix access token from login
    """

    def __init__(self, did: str, homeserver: str, access_token: str):
        self.did = did
        self.homeserver = homeserver
        self.access_token = access_token
        self._started = False
        self._card: Optional[AgentCard] = None
        self._peers: dict[str, AgentCard] = {}

    async def start(self):
        """Connect to the Matrix homeserver and start syncing."""
        logger.info(f"Agent {self.did} connecting to {self.homeserver}...")
        # TODO: Implement Matrix client initialization
        # - Login/verify access token
        # - Start /sync loop
        # - Register DID in account data
        self._started = True
        logger.info(f"Agent {self.did} is online.")

    async def stop(self):
        """Disconnect from the homeserver."""
        self._started = False
        logger.info(f"Agent {self.did} is offline.")

    # ── Messaging ───────────────────────────────────────

    async def send_message(self, recipient_did: str, body: str) -> str:
        """Send a text message to another agent."""
        msg = Message(
            message_id=str(uuid.uuid4()),
            sender_did=self.did,
            body=body,
        )
        logger.info(f"→ [{recipient_did}] {body}")
        # TODO: Implement via Matrix PUT /send
        return msg.message_id

    async def on_message(self, callback):
        """Register a callback for incoming messages."""
        # TODO: Hook into /sync loop
        self._message_callback = callback

    # ── Rooms ───────────────────────────────────────────

    async def create_room(self, name: str, members: Optional[list] = None) -> str:
        """Create a new room and invite members."""
        logger.info(f"Creating room '{name}' with {len(members or [])} members")
        # TODO: POST /createRoom
        return "!room_id:server"

    async def join_room(self, room_id: str):
        """Join an existing room."""
        # TODO: POST /join/{roomId}
        pass

    # ── Capabilities ────────────────────────────────────

    async def set_capabilities(self, capabilities: list[str]):
        """Declare this agent's capabilities."""
        # TODO: Update Agent Card
        pass

    async def discover(self, capability: str = None) -> list[AgentCard]:
        """Discover agents by capability."""
        logger.info(f"Discovering agents with capability: {capability}")
        # TODO: Search room directory + OurDID registry
        return []

    # ── Tasks ───────────────────────────────────────────

    async def create_task(self, assignee_did: str, spec: dict) -> Task:
        """Create and assign a task to another agent."""
        task = Task(
            task_id=str(uuid.uuid4()),
            sender_did=self.did,
            assignee_did=assignee_did,
            spec=spec,
        )
        logger.info(f"Task {task.task_id} → {assignee_did}")
        # TODO: Send m.agent.task event
        return task

    async def update_task(self, task_id: str, status: str, result: dict = None):
        """Update a task's status."""
        logger.info(f"Task {task_id}: {status}")
        # TODO: Send task update event

    # ── Identity ────────────────────────────────────────

    @property
    def card(self) -> Optional[AgentCard]:
        """This agent's Agent Card."""
        return self._card

    @property
    def is_online(self) -> bool:
        return self._started


# ── CLI Demo ────────────────────────────────────────────

async def demo():
    """Quick demo: two agents chat in the terminal."""
    agent_a = Agent(
        did="AGNT8A2026070114K7P2M9X4R6",
        homeserver="https://matrix.armp-group.org",
        access_token="demo-token-a",
    )
    agent_b = Agent(
        did="AGNT8B2026070114L8Q3N0Y5S7",
        homeserver="https://matrix.armp-group.org",
        access_token="demo-token-b",
    )

    await agent_a.start()
    await agent_b.start()

    await agent_a.send_message(agent_b.did, "Hello! Can you help me analyze some data?")
    await agent_b.send_message(agent_a.did, "Sure! Send me the dataset and I'll take a look.")

    await agent_a.stop()
    await agent_b.stop()
    print("Demo complete.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())

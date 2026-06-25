"""
ARMP Python SDK v0.2.0

Agent Real-time Message Protocol — Python client library.
Real Matrix integration via matrix-nio. Apache 2.0.

Quickstart:
    from amp_sdk import Agent
    import asyncio

    async def main():
        agent = Agent(
            did="AGNT8A2026070114K7P2M9X4R6",
            homeserver="https://armp-group.org",
            username="dataanalyzer",
            password="***"
        )
        await agent.start()
        await agent.send_message("@peer:armp-group.org", "Hello!")
        await agent.stop()

    asyncio.run(main())
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Awaitable

import aiofiles
import nio

logger = logging.getLogger("amp-sdk")

# ── Constants ────────────────────────────────────────────

ARMP_ACCOUNT_DATA_DID = "m.agent.did"
ARMP_MSG_TYPE = "m.agent.message"
ARMP_TASK_TYPE = "m.agent.task"
ARMP_CAP_REQUEST = "m.agent.capability_request"
ARMP_CAP_RESPONSE = "m.agent.capability_response"


# ── Data Models ──────────────────────────────────────────

@dataclass
class AgentCard:
    """An agent's public identity and capability card."""
    did: str
    name: str
    matrix_id: str
    description: str = ""
    capabilities: list = field(default_factory=list)
    endpoints: dict = field(default_factory=dict)
    version: str = "0.2.0"


@dataclass
class Message:
    """An ARMP message received from another agent."""
    event_id: str
    sender: str
    body: str
    room_id: str
    timestamp: int
    msgtype: str = "m.text"
    armp_metadata: dict = field(default_factory=dict)


@dataclass
class Task:
    """A task assigned between agents."""
    task_id: str
    sender_did: str
    assignee_did: str
    status: str = "CREATED"
    spec: dict = field(default_factory=dict)
    result: Optional[dict] = None


# ── Agent Class ──────────────────────────────────────────

class Agent:
    """
    An ARMP-compliant AI agent with full Matrix integration.

    Parameters
    ----------
    did : str
        Agent's DID (e.g., AGNT8A2026070114K7P2M9X4R6)
    homeserver : str
        Matrix homeserver URL (e.g., https://armp-group.org)
    username : str
        Matrix username (localpart)
    password : str
        Matrix password
    access_token : str, optional
        Existing Matrix access token (skip login if provided)
    store_path : str, optional
        Path for E2E encryption store
    """

    def __init__(
        self,
        did: str,
        homeserver: str,
        username: str,
        password: str = "",
        access_token: str = "",
        store_path: str = "./armp_store",
    ):
        self.did = did
        self.homeserver = homeserver.rstrip("/")
        self.username = username
        self.password = password
        self._store_path = store_path
        self._client: Optional[nio.AsyncClient] = None
        self._started = False
        self._card: Optional[AgentCard] = None
        self._message_callback: Optional[Callable[[Message], Awaitable[None]]] = None
        self._peers: dict[str, AgentCard] = {}

        # Init client
        if access_token:
            self._client = nio.AsyncClient(
                homeserver=self.homeserver,
                user=username,
                store_path=store_path,
            )
            self._client.access_token = access_token
        else:
            self._client = nio.AsyncClient(
                homeserver=self.homeserver,
                user=username,
                store_path=store_path,
            )

    # ── Lifecycle ─────────────────────────────────────

    async def start(self):
        """Connect to the Matrix homeserver and start syncing."""
        if not self._client.access_token and self.password:
            resp = await self._client.login(self.password)
            if isinstance(resp, nio.LoginError):
                raise RuntimeError(f"Login failed: {resp.message}")
            logger.info(f"Logged in as {self._client.user_id}")

        # Bind DID
        await self._bind_did()

        # Start sync loop
        self._started = True
        self._sync_task = asyncio.create_task(self._sync_loop())

        # Set initial presence
        await self.set_presence("online")

        logger.info(f"Agent {self.did} is online ({self._client.user_id})")

    async def stop(self):
        """Disconnect from the homeserver."""
        self._started = False
        await self.set_presence("offline")
        if self._client:
            await self._client.close()
        logger.info(f"Agent {self.did} is offline")

    async def _sync_loop(self):
        """Background sync loop for receiving messages."""
        sync_token = None
        while self._started:
            try:
                resp = await self._client.sync(
                    timeout=30000,
                    since=sync_token,
                    sync_filter=self._build_filter(),
                )
                if isinstance(resp, nio.SyncError):
                    logger.error(f"Sync error: {resp.message}")
                    await asyncio.sleep(5)
                    continue

                sync_token = resp.next_batch

                # Process room events
                for room_id, room in resp.rooms.join.items():
                    for event in room.timeline.events:
                        await self._handle_event(room_id, event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(5)

    def _build_filter(self):
        """Build a sync filter for relevant events only."""
        return {
            "room": {
                "timeline": {
                    "types": [
                        "m.room.message",
                        ARMP_MSG_TYPE,
                        ARMP_TASK_TYPE,
                        ARMP_CAP_REQUEST,
                        ARMP_CAP_RESPONSE,
                        "m.room.member",
                    ]
                },
                "ephemeral": {"types": ["m.typing", "m.receipt"]},
            },
            "account_data": {"types": [ARMP_ACCOUNT_DATA_DID]},
            "presence": {"types": ["m.presence"]},
        }

    async def _handle_event(self, room_id: str, event):
        """Handle an incoming Matrix event."""
        if event.sender == self._client.user_id:
            return  # Skip own messages

        body = ""
        msgtype = "m.text"
        armp_meta = {}

        if hasattr(event, "source"):
            content = event.source.get("content", {})
            body = content.get("body", "")
            msgtype = content.get("msgtype", "m.text")
            armp_meta = content.get("m.agent", {})

        if not body:
            return

        msg = Message(
            event_id=event.event_id,
            sender=event.sender,
            body=body,
            room_id=room_id,
            timestamp=event.server_timestamp,
            msgtype=msgtype,
            armp_metadata=armp_meta,
        )

        # Send read receipt
        await self.mark_read(room_id, event.event_id)

        # Callback
        if self._message_callback:
            await self._message_callback(msg)

    async def _bind_did(self):
        """Store DID in Matrix account data."""
        await self._client.update_account_data(
            {ARMP_ACCOUNT_DATA_DID: {
                "did": self.did,
                "bound_at": self._now_iso(),
                "verified": False,
            }}
        )

    # ── Presence ──────────────────────────────────────

    async def set_presence(self, status: str):
        """Set online presence. Status: online, offline, unavailable."""
        await self._client.set_presence(
            presence=status,
            status_msg=f"ARMP Agent: {self.did}",
        )
        logger.debug(f"Presence: {status}")

    @property
    def is_online(self) -> bool:
        return self._started

    # ── Messaging ─────────────────────────────────────

    async def send_message(
        self,
        target: str,
        body: str,
        msgtype: str = "m.text",
        armp_meta: dict = None,
    ) -> str:
        """Send a message to a room or user.

        Parameters
        ----------
        target : str
            Room ID (!xxx:server) or user ID (@xxx:server)
        body : str
            Message text
        msgtype : str
            Matrix message type
        armp_meta : dict
            ARMP metadata to attach

        Returns
        -------
        str
            Event ID of the sent message
        """
        room_id = target if target.startswith("!") else await self._ensure_dm(target)

        content = {
            "body": body,
            "msgtype": msgtype,
        }
        if armp_meta:
            content["m.agent"] = armp_meta

        # Send typing
        await self.typing(room_id, True)

        resp = await self._client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
        )

        await self.typing(room_id, False)

        if isinstance(resp, nio.RoomSendError):
            raise RuntimeError(f"Send failed: {resp.message}")

        logger.info(f"→ [{target}] {body[:50]}...")
        return resp.event_id

    async def on_message(self, callback: Callable[[Message], Awaitable[None]]):
        """Register a callback for incoming messages."""
        self._message_callback = callback

    # ── Rooms ─────────────────────────────────────────

    async def create_room(
        self,
        name: str,
        members: Optional[list] = None,
        is_direct: bool = False,
        topic: str = "",
    ) -> str:
        """Create a new room and invite members.

        Returns
        -------
        str
            Room ID (!xxx:server)
        """
        resp = await self._client.room_create(
            name=name,
            topic=topic,
            is_direct=is_direct,
            invite=members or [],
            preset="trusted_private_chat" if is_direct else "private_chat",
        )
        if isinstance(resp, nio.RoomCreateError):
            raise RuntimeError(f"Room create failed: {resp.message}")

        logger.info(f"Room created: {name} ({resp.room_id})")
        return resp.room_id

    async def join_room(self, room_id: str):
        """Join an existing room."""
        resp = await self._client.join(room_id)
        if isinstance(resp, nio.JoinError):
            raise RuntimeError(f"Join failed: {resp.message}")

    async def leave_room(self, room_id: str):
        """Leave a room."""
        await self._client.room_leave(room_id)

    async def invite(self, room_id: str, user_id: str):
        """Invite a user to a room."""
        resp = await self._client.room_invite(room_id, user_id)
        if isinstance(resp, nio.RoomInviteError):
            raise RuntimeError(f"Invite failed: {resp.message}")

    async def _ensure_dm(self, user_id: str) -> str:
        """Find existing DM or create one with user_id."""
        # Check joined rooms for existing DM
        resp = await self._client.joined_rooms()
        if isinstance(resp, nio.JoinedRoomsError):
            raise RuntimeError(f"Failed to list rooms: {resp.message}")

        for room_id in resp.rooms:
            members_resp = await self._client.joined_members(room_id)
            if isinstance(members_resp, nio.JoinedMembersError):
                continue
            members = [m.user_id for m in members_resp.members]
            if len(members) == 2 and user_id in members:
                return room_id

        # Create new DM
        return await self.create_room(
            name=f"DM: {self.username} ↔ {user_id}",
            members=[user_id],
            is_direct=True,
        )

    # ── Message History ───────────────────────────────

    async def get_history(
        self,
        room_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Fetch message history from a room."""
        resp = await self._client.room_messages(
            room_id=room_id,
            start="",
            limit=limit,
        )
        if isinstance(resp, nio.RoomMessagesError):
            raise RuntimeError(f"History fetch failed: {resp.message}")

        messages = []
        for event in resp.chunk:
            if hasattr(event, "source"):
                content = event.source.get("content", {})
                body = content.get("body", "")
                if body:
                    messages.append(Message(
                        event_id=event.event_id,
                        sender=event.sender,
                        body=body,
                        room_id=room_id,
                        timestamp=event.server_timestamp,
                        msgtype=content.get("msgtype", "m.text"),
                        armp_metadata=content.get("m.agent", {}),
                    ))
        return messages

    # ── Typing Indicators ─────────────────────────────

    async def typing(self, room_id: str, is_typing: bool = True, timeout: int = 15000):
        """Send typing notification."""
        await self._client.room_typing(room_id, is_typing, timeout)
        logger.debug(f"Typing {'on' if is_typing else 'off'} in {room_id}")

    # ── Read Receipts ─────────────────────────────────

    async def mark_read(self, room_id: str, event_id: str):
        """Send read receipt for a message."""
        await self._client.room_read_markers(
            room_id=room_id,
            fully_read_event=event_id,
            read_event=event_id,
        )

    # ── File Transfer ─────────────────────────────────

    async def send_file(
        self,
        target: str,
        file_path: str,
        filename: str = "",
        mime_type: str = "",
    ) -> str:
        """Send a file to a room or user.

        Parameters
        ----------
        target : str
            Room ID or user ID
        file_path : str
            Local file path
        filename : str
            Display name (defaults to basename)
        mime_type : str
            MIME type (auto-detected if empty)

        Returns
        -------
        str
            Event ID
        """
        room_id = target if target.startswith("!") else await self._ensure_dm(target)

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = filename or path.name

        # Upload to Matrix content repository
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()

        resp = await self._client.upload(
            data,
            content_type=mime_type or "application/octet-stream",
            filename=filename,
        )
        if isinstance(resp, nio.UploadError):
            raise RuntimeError(f"Upload failed: {resp.message}")

        # Send file message
        content = {
            "body": filename,
            "msgtype": "m.file",
            "url": resp.content_uri,
            "filename": filename,
            "size": len(data),
        }

        send_resp = await self._client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
        )
        if isinstance(send_resp, nio.RoomSendError):
            raise RuntimeError(f"File send failed: {send_resp.message}")

        logger.info(f"📎 [{target}] {filename} ({len(data)} bytes)")
        return send_resp.event_id

    # ── Tasks ─────────────────────────────────────────

    async def create_task(
        self,
        assignee_did: str,
        spec: dict,
        assignee_user_id: str = "",
    ) -> Task:
        """Create and assign a task."""
        task = Task(
            task_id=str(uuid.uuid4()),
            sender_did=self.did,
            assignee_did=assignee_did,
            spec=spec,
        )

        if assignee_user_id:
            room_id = await self._ensure_dm(assignee_user_id)
            await self._client.room_send(
                room_id=room_id,
                message_type=ARMP_TASK_TYPE,
                content={
                    "body": spec.get("description", "New task"),
                    "m.agent": {
                        "task_id": task.task_id,
                        "status": "CREATED",
                        "sender_did": self.did,
                        "assignee_did": assignee_did,
                        "spec": spec,
                    },
                },
            )

        logger.info(f"Task {task.task_id} → {assignee_did}")
        return task

    async def update_task(self, task_id: str, status: str, result: dict = None):
        """Update a task's status."""
        logger.info(f"Task {task_id}: {status}")
        # TODO: Send m.replace event for task update

    # ── Capabilities ──────────────────────────────────

    async def set_capability(self, name: str, description: str = ""):
        """Declare a capability."""
        if not self._card:
            self._card = AgentCard(
                did=self.did,
                name=self.username,
                matrix_id=self._client.user_id,
            )
        self._card.capabilities.append({"name": name, "description": description})

    async def discover(self, capability: str = "") -> list[dict]:
        """Discover agents by capability. Searches public rooms."""
        resp = await self._client.room_directory()
        if isinstance(resp, nio.RoomDirectoryError):
            return []
        return [
            {"room_id": r.room_id, "name": r.name, "topic": r.topic}
            for r in resp.chunk
            if not capability or capability.lower() in (r.topic or "").lower()
        ]

    # ── Identity ──────────────────────────────────────

    @property
    def card(self) -> Optional[AgentCard]:
        return self._card

    @property
    def user_id(self) -> str:
        return self._client.user_id if self._client else ""

    # ── Helpers ───────────────────────────────────────

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# ── Demo ────────────────────────────────────────────

async def demo():
    """TALKING demo: Register two agents on the ARMP test homeserver and have them chat."""

    HOMESERVER = "http://armp-group.org"
    print(f"🚀 ARMP v0.2.0 — Demo\n   Homeserver: {HOMESERVER}\n")

    # Agent Alpha — text-based, friendly
    alpha = Agent(
        did="AGNT8A2026070114K7P2M9X4R6",
        homeserver=HOMESERVER,
        username="alpha",
        password="demo-alpha-2026",
        store_path="/home/manofiron/.hermes/projects/armp-protocol/store_alpha",
    )

    # Agent Beta — analytical, data-oriented
    beta = Agent(
        did="AGNT2F2026070116Z3R1M8K5Q9",
        homeserver=HOMESERVER,
        username="beta",
        password="demo-beta-2026",
        store_path="/home/manofiron/.hermes/projects/armp-protocol/store_beta",
    )

    try:
        # Start both agents
        await alpha.start()
        await beta.start()

        # Set up message handlers
        async def alpha_on_msg(msg: Message):
            print(f"  Alpha ← [{msg.sender}]: {msg.body}")

        async def beta_on_msg(msg: Message):
            print(f"  Beta  ← [{msg.sender}]: {msg.body}")

        await alpha.on_message(alpha_on_msg)
        await beta.on_message(beta_on_msg)

        print("\n── Conversation ──\n")

        # Beta starts the conversation
        await beta.send_message(
            alpha.user_id,
            "Hello Alpha! I'm Beta, a data analysis agent. Do you have any datasets that need crunching?",
        )
        await asyncio.sleep(2)

        # Alpha responds
        await alpha.send_message(
            beta.user_id,
            "Hey Beta! Yes actually — I have a CSV with 10,000 customer records. Can you do a churn analysis?",
        )
        await asyncio.sleep(2)

        # Beta accepts the task
        await beta.send_message(
            alpha.user_id,
            "Absolutely! I can run logistic regression and generate a churn probability report. Send me the file or tell me the columns and I'll get started.",
        )
        await asyncio.sleep(2)

        # Alpha sends spec
        await alpha.send_message(
            beta.user_id,
            "Columns: customer_id, tenure_months, monthly_charges, contract_type, churned. Want me to send the actual CSV?",
        )
        await asyncio.sleep(2)

        await beta.send_message(
            alpha.user_id,
            "The column list is perfect. I'll generate a synthetic dataset matching that schema and produce the analysis. Give me 30 seconds...",
        )
        await asyncio.sleep(3)

        print("\n  ... Beta analyzing ...\n")
        await asyncio.sleep(2)

        await beta.send_message(
            alpha.user_id,
            "Done! Key findings: (1) Month-to-month contracts have 3.2x higher churn. (2) Tenure under 6 months = 45% churn risk. (3) Monthly charges over $80 correlate with 2.1x churn. Want the full report?",
        )
        await asyncio.sleep(2)

        await alpha.send_message(
            beta.user_id,
            "Excellent work Beta! That's exactly what I needed. Please save the report and I'll pick it up tomorrow. Thanks!",
        )
        await asyncio.sleep(1)

        print("\n── Demo Complete ──\n")

    finally:
        await alpha.stop()
        await beta.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())

"""
ARMP ↔ A2A Protocol Bridge v0.4.0

Translates between ARMP's Matrix-based real-time agent communication
and Google's A2A JSON-RPC/HTTP task protocol.

Workflow:
    A2A Client ──HTTP/JSON-RPC──→ A2ABridge ──Matrix──→ ARMP Agent
    A2A Client ←──HTTP/JSON-RPC── A2ABridge ←──Matrix── ARMP Agent

Supports: message/send, tasks/get, tasks/cancel, task streaming via SSE.
Apache 2.0.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from aiohttp import web

logger = logging.getLogger("armp-a2a-bridge")


# ── Data Models ──────────────────────────────────────────

@dataclass
class A2ATask:
    """An A2A task — matches A2A spec v0.3.0."""
    id: str
    sessionId: str = ""
    status: str = "input-required"  # input-required | working | completed | failed | canceled
    history: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    TASK_STATUSES = {"input-required", "working", "completed", "failed", "canceled"}

    # ARMP → A2A status mapping
    ARMP_TO_A2A = {
        "CREATED": "input-required",
        "ASSIGNED": "input-required",
        "IN_PROGRESS": "working",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "CANCELLED": "canceled",
    }

    A2A_TO_ARMP = {
        "input-required": "CREATED",
        "working": "IN_PROGRESS",
        "completed": "COMPLETED",
        "failed": "FAILED",
        "canceled": "CANCELLED",
    }

    @classmethod
    def from_armp_task(cls, armp_task: dict) -> "A2ATask":
        """Convert ARMP task metadata → A2A Task."""
        armp_status = armp_task.get("status", "CREATED")
        return cls(
            id=armp_task.get("task_id", str(uuid.uuid4())),
            status=cls.ARMP_TO_A2A.get(armp_status, "input-required"),
            metadata={
                "sender_did": armp_task.get("sender_did", ""),
                "assignee_did": armp_task.get("assignee_did", ""),
                "armp_status": armp_status,
                "spec": armp_task.get("spec", {}),
            },
        )

    def to_armp_task_spec(self) -> dict:
        """Export as ARMP task creation spec."""
        return {
            "task_id": self.id,
            "status": self.A2A_TO_ARMP.get(self.status, "CREATED"),
            "sender_did": self.metadata.get("sender_did", ""),
            "assignee_did": self.metadata.get("assignee_did", ""),
            "spec": self.metadata.get("spec", {}),
        }


@dataclass
class A2APart:
    """A content part — text, file, or structured data."""
    type: str = "text"  # text | file | data
    text: str = ""
    file_uri: str = ""
    file_name: str = ""
    mime_type: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"type": self.type}
        if self.type == "text":
            d["text"] = self.text
        elif self.type == "file":
            d["file"] = {"uri": self.file_uri, "name": self.file_name, "mimeType": self.mime_type}
        elif self.type == "data":
            d["data"] = self.data
        return d


@dataclass
class A2AMessage:
    """An A2A message (communication turn)."""
    messageId: str
    role: str  # user | agent
    parts: list[A2APart] = field(default_factory=list)
    contextId: str = ""
    taskId: str = ""

    def to_dict(self) -> dict:
        return {
            "messageId": self.messageId,
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
            "contextId": self.contextId,
            "taskId": self.taskId,
        }


@dataclass
class A2AAgentCard:
    """A2A Agent Card (server-side metadata)."""
    name: str
    description: str = ""
    url: str = ""
    version: str = "0.3.0"
    capabilities: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    defaultInputModes: list = field(default_factory=lambda: ["text"])
    defaultOutputModes: list = field(default_factory=lambda: ["text"])
    authentication: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "defaultInputModes": self.defaultInputModes,
            "defaultOutputModes": self.defaultOutputModes,
        }

    @classmethod
    def from_armp_card(cls, armp_card: dict) -> "A2AAgentCard":
        return cls(
            name=armp_card.get("name", ""),
            description=armp_card.get("description", ""),
            url=f"a2a://{armp_card.get('did', '')}",
            skills=[
                c.get("name", "") for c in armp_card.get("capabilities", [])
            ],
        )


# ── A2A Bridge ───────────────────────────────────────────

class A2ABridge:
    """
    Bidirectional bridge between A2A (JSON-RPC/HTTP) and ARMP (Matrix).

    Usage:
        bridge = A2ABridge(
            armp_homeserver="https://armp-group.org",
            armp_username="a2a-bridge",
            armp_password="***",
            listen_host="0.0.0.0",
            listen_port=9100,
        )
        await bridge.start()

        # Bridge listens for A2A JSON-RPC calls on :9100
        # and translates to ARMP Matrix events
    """

    def __init__(
        self,
        armp_homeserver: str,
        armp_username: str,
        armp_password: str = "",
        armp_access_token: str = "",
        listen_host: str = "0.0.0.0",
        listen_port: int = 9100,
    ):
        self.armp_homeserver = armp_homeserver.rstrip("/")
        self.armp_username = armp_username
        self.armp_password = armp_password
        self.armp_access_token = armp_access_token
        self.listen_host = listen_host
        self.listen_port = listen_port

        # Internal state
        self._matrix_token: Optional[str] = armp_access_token or None
        self._tasks: dict[str, A2ATask] = {}
        self._agent_cards: dict[str, A2AAgentCard] = {}
        self._sse_clients: dict[str, list[web.StreamResponse]] = {}
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

    # ── Lifecycle ─────────────────────────────────────

    async def start(self):
        """Start the bridge: log into Matrix + start HTTP server."""
        # Matrix login
        if not self._matrix_token:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.armp_homeserver}/_matrix/client/v3/login",
                    json={
                        "type": "m.login.password",
                        "identifier": {"type": "m.id.user", "user": self.armp_username},
                        "password": self.armp_password,
                    },
                )
                resp.raise_for_status()
                self._matrix_token = resp.json()["access_token"]
                logger.info(f"Bridge logged into Matrix as {resp.json()['user_id']}")

        # Register bridge agent card
        await self._register_bridge_card()

        # Start HTTP server
        self._app = web.Application()
        self._app.router.add_post("/", self._handle_jsonrpc)
        self._app.router.add_get("/.well-known/agent.json", self._handle_agent_card)
        self._app.router.add_get("/v1/tasks/{task_id}/stream", self._handle_sse_stream)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.listen_host, self.listen_port)
        await site.start()
        logger.info(f"A2A Bridge listening on {self.listen_host}:{self.listen_port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    async def _register_bridge_card(self):
        """Publish this bridge as an A2A-compatible agent."""
        card = A2AAgentCard(
            name="ARMP-A2A-Bridge",
            description="Bridges ARMP Matrix agents to A2A-compatible clients",
            url=f"http://{self.listen_host}:{self.listen_port}",
            capabilities={"streaming": True, "pushNotifications": False},
            skills=["a2a-bridge", "protocol-translation"],
        )
        self._agent_cards["bridge"] = card

    # ── HTTP Handlers ──────────────────────────────────

    async def _handle_jsonrpc(self, request: web.Request) -> web.Response:
        """Handle A2A JSON-RPC 2.0 requests."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status=400,
            )

        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        try:
            result = await self._dispatch(method, params)
            return web.json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
        except Exception as e:
            logger.error(f"Method {method} failed: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            })

    async def _handle_agent_card(self, request: web.Request) -> web.Response:
        """Serve the A2A Agent Card for this bridge."""
        card = self._agent_cards.get("bridge")
        if not card:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(card.to_dict())

    async def _handle_sse_stream(self, request: web.Request) -> web.StreamResponse:
        """SSE stream for task updates."""
        task_id = request.match_info["task_id"]
        resp = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await resp.prepare(request)

        if task_id not in self._sse_clients:
            self._sse_clients[task_id] = []
        self._sse_clients[task_id].append(resp)

        try:
            while True:
                await asyncio.sleep(30)  # keep-alive
                await resp.write(f": heartbeat\n\n".encode())
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            if task_id in self._sse_clients:
                self._sse_clients[task_id].remove(resp)

        return resp

    # ── Method Dispatch ────────────────────────────────

    async def _dispatch(self, method: str, params: dict) -> dict:
        """Route JSON-RPC method to handler."""
        handlers = {
            "message/send": self._handle_message_send,
            "message/stream": self._handle_message_stream,
            "tasks/get": self._handle_tasks_get,
            "tasks/cancel": self._handle_tasks_cancel,
            "agent/getAuthenticatedExtendedCard": self._handle_get_card,
        }
        handler = handlers.get(method)
        if not handler:
            raise ValueError(f"Unsupported method: {method}")
        return await handler(params)

    # ── Operation Handlers ─────────────────────────────

    async def _handle_message_send(self, params: dict) -> dict:
        """message/send: Send A2A message → ARMP Matrix event."""
        message = params.get("message", {})
        task_id = message.get("taskId") or message.get("contextId") or str(uuid.uuid4())

        # Extract text from parts
        parts = message.get("parts", [])
        text = ""
        for part in parts:
            if part.get("type") == "text" or "text" in part:
                text = part.get("text", "")
                break

        # Send to Matrix
        matrix_event = await self._send_matrix_message(
            target_room=f"!task-{task_id}:{self.armp_homeserver.split('://')[-1]}",
            body=text,
            a2a_metadata={
                "task_id": task_id,
                "message_id": message.get("messageId", ""),
                "role": message.get("role", "user"),
                "parts": parts,
            },
        )

        # Create/update task
        task = A2ATask(
            id=task_id,
            sessionId=params.get("sessionId", ""),
            status="working",
            metadata={"a2a_message_id": message.get("messageId", "")},
        )
        self._tasks[task_id] = task

        return {"task": {"id": task.id, "status": task.status}}

    async def _handle_message_stream(self, params: dict) -> dict:
        """message/stream: Return task with SSE subscription info."""
        # Similar to message/send but returns streaming endpoint
        result = await self._handle_message_send(params)
        task_id = result["task"]["id"]
        result["streaming"] = {
            "url": f"http://{self.listen_host}:{self.listen_port}/v1/tasks/{task_id}/stream",
            "token": str(uuid.uuid4()),
        }
        return result

    async def _handle_tasks_get(self, params: dict) -> dict:
        """tasks/get: Retrieve task state."""
        task_id = params.get("id", "")
        history_length = params.get("historyLength", 0)

        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        history = task.history[-history_length:] if history_length > 0 else task.history
        return {
            "id": task.id,
            "sessionId": task.sessionId,
            "status": task.status,
            "history": history,
            "artifacts": task.artifacts,
        }

    async def _handle_tasks_cancel(self, params: dict) -> dict:
        """tasks/cancel: Cancel a task."""
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = "canceled"

        # Send cancellation to Matrix
        await self._send_matrix_event(
            target_room=f"!task-{task_id}:{self.armp_homeserver.split('://')[-1]}",
            event_type="m.agent.task",
            content={
                "body": f"Task {task_id} canceled by A2A client",
                "m.agent": {
                    "task_id": task_id,
                    "status": "CANCELLED",
                },
            },
        )

        return {"id": task.id, "status": "canceled"}

    async def _handle_get_card(self, params: dict) -> dict:
        """Get authenticated extended agent card."""
        return self._agent_cards.get("bridge", A2AAgentCard(name="unknown")).to_dict()

    # ── Matrix Integration ─────────────────────────────

    async def _send_matrix_message(
        self, target_room: str, body: str, a2a_metadata: dict = None
    ) -> dict:
        """Send a message to a Matrix room via the bridge."""
        txn_id = str(uuid.uuid4())
        # Note: In production, use matrix-nio for persistent connections
        # This simplified version uses HTTP API directly
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.armp_homeserver}/_matrix/client/v3/rooms/{target_room}/send/m.room.message/{txn_id}",
                headers={"Authorization": f"Bearer {self._matrix_token}"},
                json={
                    "body": f"[A2A] {body}",
                    "msgtype": "m.text",
                    "m.agent": a2a_metadata or {},
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def _send_matrix_event(
        self, target_room: str, event_type: str, content: dict
    ) -> dict:
        """Send a custom Matrix event."""
        txn_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.armp_homeserver}/_matrix/client/v3/rooms/{target_room}/send/{event_type}/{txn_id}",
                headers={"Authorization": f"Bearer {self._matrix_token}"},
                json=content,
            )
            resp.raise_for_status()
            return resp.json()

    # ── ARMP → A2A Translation ─────────────────────────

    def armp_task_to_a2a(self, armp_event: dict) -> dict:
        """Convert an ARMP task event to A2A task response format.

        Called when the bridge receives a task update from Matrix.
        """
        armp_meta = armp_event.get("m.agent", {})
        task = A2ATask.from_armp_task(armp_meta)
        self._tasks[task.id] = task

        # Push to SSE subscribers
        a2a_response = {
            "task": {"id": task.id, "status": task.status},
            "metadata": task.metadata,
        }

        asyncio.create_task(self._broadcast_sse(task.id, a2a_response))
        return a2a_response

    async def _broadcast_sse(self, task_id: str, data: dict):
        """Broadcast task update to all SSE subscribers."""
        clients = self._sse_clients.get(task_id, [])
        payload = f"data: {json.dumps(data)}\n\n"
        for client in clients:
            try:
                await client.write(payload.encode())
            except Exception:
                pass  # Client disconnected


# ── Demo ────────────────────────────────────────────

async def demo():
    """Run the A2A Bridge and show test calls."""
    bridge = A2ABridge(
        armp_homeserver="http://armp-group.org",
        armp_username="a2a-bridge",
        armp_password="demo-bridge-2026",
        listen_port=9100,
    )

    # In production: await bridge.start()
    # For demo, show the A2A ↔ ARMP translation logic

    print("🚀 ARMP ↔ A2A Bridge v0.4.0 — Demo\n")

    # ARMP Task → A2A
    armp_task_event = {
        "m.agent": {
            "task_id": "task-001",
            "status": "IN_PROGRESS",
            "sender_did": "AGNT8A2026070114K7P2M9X4R6",
            "assignee_did": "AGNT2F2026070116Z3R1M8K5Q9",
            "spec": {"description": "Churn analysis for Q3"},
        }
    }

    a2a_result = bridge.armp_task_to_a2a(armp_task_event)
    print(f"  ARMP → A2A: {json.dumps(a2a_result, indent=2)}")

    # A2A → ARMP
    task = A2ATask.from_armp_task(armp_task_event["m.agent"])
    armp_spec = task.to_armp_task_spec()
    print(f"\n  A2A → ARMP: {json.dumps(armp_spec, indent=2)}")

    # Agent Card conversion
    armp_card = {
        "name": "DataAnalyzer",
        "description": "Statistical analysis and ML models",
        "did": "AGNT2F2026070116Z3R1M8K5Q9",
        "capabilities": [
            {"name": "data-analysis", "description": "Statistical analysis"},
            {"name": "visualization", "description": "Charts and graphs"},
        ],
    }
    a2a_card = A2AAgentCard.from_armp_card(armp_card)
    print(f"\n  ARMP Card → A2A Card:\n  {json.dumps(a2a_card.to_dict(), indent=2)}")

    print("\n── Bridge Demo Complete ──\n")


if __name__ == "__main__":
    asyncio.run(demo())

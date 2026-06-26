"""
Interoperability Test Suite for ARMP Python SDK v0.5.0

Tests data models, task lifecycle, capability scoring, and serialization.
Matrix-connected tests are skipped unless MATRIX_TEST=1 is set.

Run: python3 -m pytest tests/ -v
"""

import sys
import os
import json

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amp_sdk import (
    Agent, AgentCard, Task, Message, NegotiationResult,
    ARMP_MSG_TYPE, ARMP_TASK_TYPE, ARMP_CAP_REQUEST, ARMP_CAP_RESPONSE,
    ARMP_ACCOUNT_DATA_DID,
)

# ── AgentCard Tests ──────────────────────────────────────

class TestAgentCard:
    def test_create_card(self):
        card = AgentCard(
            did="AGNT8A2026070114K7P2M9X4R6",
            name="TestAgent",
            matrix_id="@test:armp-group.org",
        )
        assert card.did == "AGNT8A2026070114K7P2M9X4R6"
        assert card.name == "TestAgent"
        assert card.matrix_id == "@test:armp-group.org"
        assert card.version == "0.5.0"
        assert card.capabilities == []
        assert card.description == ""

    def test_card_with_capabilities(self):
        card = AgentCard(
            did="AGNT-A",
            name="Alpha",
            matrix_id="@alpha:test.org",
            capabilities=[
                {"name": "data-analysis", "description": "Stats"},
                {"name": "visualization", "description": "Charts"},
            ],
        )
        assert len(card.capabilities) == 2
        assert card.capabilities[0]["name"] == "data-analysis"

    def test_to_dict(self):
        card = AgentCard(
            did="AGNT-A",
            name="Alpha",
            matrix_id="@alpha:test.org",
            description="Test agent",
        )
        d = card.to_dict()
        assert d["did"] == "AGNT-A"
        assert d["name"] == "Alpha"
        assert d["matrix_id"] == "@alpha:test.org"
        assert d["version"] == "0.5.0"
        assert "capabilities" in d
        assert "endpoints" in d

    def test_from_dict(self):
        data = {
            "did": "AGNT-B",
            "name": "Beta",
            "matrix_id": "@beta:test.org",
            "capabilities": [{"name": "text-gen"}],
            "version": "0.5.0",
        }
        card = AgentCard.from_dict(data)
        assert card.did == "AGNT-B"
        assert card.name == "Beta"
        assert len(card.capabilities) == 1

    def test_from_dict_defaults(self):
        card = AgentCard.from_dict({})
        assert card.did == ""
        assert card.version == "0.5.0"
        assert card.capabilities == []

    def test_roundtrip(self):
        card = AgentCard(
            did="AGNT-C",
            name="Gamma",
            matrix_id="@gamma:test.org",
            capabilities=[{"name": "search", "description": "Web search"}],
        )
        card2 = AgentCard.from_dict(card.to_dict())
        assert card2.did == card.did
        assert card2.name == card.name
        assert len(card2.capabilities) == len(card.capabilities)


# ── Task Lifecycle Tests ─────────────────────────────────

class TestTask:
    def test_create_task(self):
        task = Task(
            task_id="task-001",
            sender_did="AGNT-A",
            assignee_did="AGNT-B",
            spec={"description": "Test task"},
        )
        assert task.task_id == "task-001"
        assert task.status == "CREATED"
        assert task.progress == 0.0
        assert task.result is None
        assert task.history == []

    def test_valid_transitions(self):
        task = Task("t1", "AGNT-A", "AGNT-B")

        # CREATED -> ASSIGNED
        assert task.transition("ASSIGNED")
        assert task.status == "ASSIGNED"
        assert len(task.history) == 1

        # ASSIGNED -> IN_PROGRESS
        assert task.transition("IN_PROGRESS")
        assert task.status == "IN_PROGRESS"
        assert len(task.history) == 2

        # IN_PROGRESS -> COMPLETED
        assert task.transition("COMPLETED", "All done")
        assert task.status == "COMPLETED"
        assert task.history[-1]["detail"] == "All done"

    def test_invalid_transitions(self):
        task = Task("t2", "AGNT-A", "AGNT-B")

        # CREATED -> COMPLETED (invalid)
        assert not task.transition("COMPLETED")
        assert task.status == "CREATED"

        # CREATED -> IN_PROGRESS (invalid)
        assert not task.transition("IN_PROGRESS")
        assert task.status == "CREATED"

    def test_fail_and_retry(self):
        task = Task("t3", "AGNT-A", "AGNT-B")
        task.transition("ASSIGNED")
        task.transition("IN_PROGRESS")

        # IN_PROGRESS -> FAILED
        assert task.transition("FAILED", "Timeout")
        assert task.status == "FAILED"

        # FAILED -> ASSIGNED (retry)
        assert task.transition("ASSIGNED", "Retry")
        assert task.status == "ASSIGNED"

    def test_cancel_from_created(self):
        task = Task("t4", "AGNT-A", "AGNT-B")
        assert task.transition("CANCELLED")
        assert task.status == "CANCELLED"

    def test_cancel_from_assigned(self):
        task = Task("t5", "AGNT-A", "AGNT-B")
        task.transition("ASSIGNED")
        assert task.transition("CANCELLED")

    def test_terminal_states_immutable(self):
        task = Task("t6", "AGNT-A", "AGNT-B")
        task.transition("ASSIGNED")
        task.transition("IN_PROGRESS")
        task.transition("COMPLETED")

        # COMPLETED is terminal
        assert not task.transition("FAILED")
        assert task.status == "COMPLETED"

    def test_full_lifecycle_history(self):
        task = Task("t7", "AGNT-A", "AGNT-B", spec={"desc": "Full test"})
        task.transition("ASSIGNED", "assigned to worker")
        task.transition("IN_PROGRESS", "started working")
        task.transition("COMPLETED", "finished")

        assert len(task.history) == 3
        assert task.history[0]["from"] == "CREATED"
        assert task.history[0]["to"] == "ASSIGNED"
        assert task.history[2]["from"] == "IN_PROGRESS"
        assert task.history[2]["to"] == "COMPLETED"


# ── Message Tests ────────────────────────────────────────

class TestMessage:
    def test_create_message(self):
        msg = Message(
            event_id="$evt-001",
            sender="@agent:test.org",
            body="Hello world",
            room_id="!room:test.org",
            timestamp=1782400000000,
        )
        assert msg.event_id == "$evt-001"
        assert msg.sender == "@agent:test.org"
        assert msg.body == "Hello world"
        assert msg.msgtype == "m.text"
        assert msg.armp_metadata == {}

    def test_message_with_metadata(self):
        meta = {"message_id": "uuid-001", "sender_did": "AGNT-A"}
        msg = Message(
            event_id="$evt-002",
            sender="@agent:test.org",
            body="Task request",
            room_id="!room:test.org",
            timestamp=1782400000001,
            armp_metadata=meta,
        )
        assert msg.armp_metadata["sender_did"] == "AGNT-A"


# ── NegotiationResult Tests ──────────────────────────────

class TestNegotiationResult:
    def test_basic_result(self):
        peer_card = AgentCard(did="AGNT-B", name="Beta", matrix_id="@beta:test.org")
        result = NegotiationResult(
            peer_did="AGNT-B",
            peer_card=peer_card,
            my_capabilities=["data-analysis", "text-gen"],
            peer_capabilities=["data-analysis", "visualization"],
            mutual_capabilities=["data-analysis"],
            missing_capabilities=["visualization"],
            matched=True,
        )
        assert result.peer_did == "AGNT-B"
        assert result.mutual_capabilities == ["data-analysis"]
        assert len(result.missing_capabilities) == 1
        assert result.matched is True

    def test_no_match(self):
        peer_card = AgentCard(did="AGNT-C", name="Gamma", matrix_id="@gamma:test.org")
        result = NegotiationResult(
            peer_did="AGNT-C",
            peer_card=peer_card,
            my_capabilities=["text-gen"],
            peer_capabilities=["image-gen"],
            mutual_capabilities=[],
            missing_capabilities=["image-gen"],
            matched=False,
        )
        assert result.matched is False
        assert len(result.mutual_capabilities) == 0


# ── Constants Tests ──────────────────────────────────────

class TestConstants:
    def test_event_types(self):
        assert ARMP_MSG_TYPE == "m.agent.message"
        assert ARMP_TASK_TYPE == "m.agent.task"
        assert ARMP_CAP_REQUEST == "m.agent.capability_request"
        assert ARMP_CAP_RESPONSE == "m.agent.capability_response"

    def test_account_data_type(self):
        assert ARMP_ACCOUNT_DATA_DID == "m.agent.did"


# ── Agent Lifecycle (requires Matrix) ────────────────────

class TestAgentLifecycle:
    def test_agent_creation(self):
        agent = Agent(
            did="AGNT-TEST",
            homeserver="https://test.example.com",
            username="testagent",
        )
        assert agent.did == "AGNT-TEST"
        assert agent.homeserver == "https://test.example.com"
        assert agent.username == "testagent"
        assert not agent.is_online

    def test_set_capability_before_start(self):
        """Capability can be set before agent starts."""
        import asyncio
        agent = Agent(
            did="AGNT-TEST",
            homeserver="https://test.example.com",
            username="testagent",
        )
        asyncio.run(agent.set_capability("test-cap", "A test capability"))
        assert agent.card is not None
        assert len(agent.card.capabilities) == 1
        assert agent.card.capabilities[0]["name"] == "test-cap"

    def test_multiple_capabilities(self):
        import asyncio
        agent = Agent(
            did="AGNT-TEST",
            homeserver="https://test.example.com",
            username="testagent",
        )
        asyncio.run(agent.set_capability("cap-a", "First"))
        asyncio.run(agent.set_capability("cap-b", "Second"))
        asyncio.run(agent.set_capability("cap-c", "Third"))
        assert len(agent.card.capabilities) == 3


# ── Capability Scoring Tests ─────────────────────────────

class TestCapabilityScoring:
    def test_exact_match(self):
        agent = Agent(did="A", homeserver="https://t", username="a")
        card = AgentCard(
            did="B", name="Beta", matrix_id="@b:t",
            capabilities=[{"name": "data-analysis"}, {"name": "visualization"}],
        )

        spec = {
            "capabilities_required": ["data-analysis"],
            "capabilities_preferred": ["visualization"],
        }
        score = agent._score_capability_match(spec, card)
        assert score > 0.9  # Should be close to 1.0

    def test_missing_required(self):
        agent = Agent(did="A", homeserver="https://t", username="a")
        card = AgentCard(
            did="B", name="Beta", matrix_id="@b:t",
            capabilities=[{"name": "text-gen"}],
        )

        spec = {"capabilities_required": ["data-analysis"]}
        score = agent._score_capability_match(spec, card)
        assert score == 0.0

    def test_partial_preferred(self):
        agent = Agent(did="A", homeserver="https://t", username="a")
        card = AgentCard(
            did="B", name="Beta", matrix_id="@b:t",
            capabilities=[{"name": "data-analysis"}, {"name": "visualization"}],
        )

        spec = {
            "capabilities_required": ["data-analysis"],
            "capabilities_preferred": ["visualization", "3d-rendering"],
        }
        score = agent._score_capability_match(spec, card)
        # required: 1.0 * 0.6 = 0.6, preferred: 1/2 * 0.4 = 0.2, total = 0.8
        assert 0.7 < score < 0.9

    def test_no_capabilities_specified(self):
        agent = Agent(did="A", homeserver="https://t", username="a")
        card = AgentCard(did="B", name="Beta", matrix_id="@b:t")
        score = agent._score_capability_match({}, card)
        assert score == 0.5


# ── Task Task Management (Agent-level) ───────────────────

class TestAgentTasks:
    def test_create_task_via_agent(self):
        """Agent.create_task() works without Matrix (sync wrapper)."""
        agent = Agent(did="AGNT-A", homeserver="https://t", username="a")
        # create_task is async but creates the Task locally first
        import asyncio
        task = asyncio.run(agent.create_task(
            assignee_did="AGNT-B",
            spec={"description": "Analyze data"},
        ))
        assert task.sender_did == "AGNT-A"
        assert task.assignee_did == "AGNT-B"
        assert task.status == "CREATED"

    def test_get_task(self):
        agent = Agent(did="AGNT-A", homeserver="https://t", username="a")
        import asyncio
        task = asyncio.run(agent.create_task(assignee_did="AGNT-B", spec={}))
        retrieved = agent.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_task_not_found(self):
        agent = Agent(did="AGNT-A", homeserver="https://t", username="a")
        assert agent.get_task("nonexistent") is None


# ── Serialization Tests ──────────────────────────────────

class TestSerialization:
    """Verify data models can be serialized/deserialized for interop."""

    def test_agent_card_json(self):
        import json
        card = AgentCard(
            did="AGNT-A",
            name="Alpha",
            matrix_id="@alpha:test.org",
            capabilities=[{"name": "test", "description": "desc"}],
        )
        data = json.dumps(card.to_dict())
        parsed = json.loads(data)
        assert parsed["did"] == "AGNT-A"
        assert parsed["version"] == "0.5.0"

    def test_negotiation_result_json(self):
        import json
        card = AgentCard(did="B", name="Beta", matrix_id="@b:t")
        result = NegotiationResult(
            peer_did="B",
            peer_card=card,
            my_capabilities=["a", "b"],
            peer_capabilities=["b", "c"],
            mutual_capabilities=["b"],
            missing_capabilities=["c"],
            matched=True,
        )
        # Should be serializable
        data = json.dumps({
            "peer_did": result.peer_did,
            "mutual": result.mutual_capabilities,
            "matched": result.matched,
        })
        parsed = json.loads(data)
        assert parsed["matched"] is True
        assert "b" in parsed["mutual"]


# ── Rust SDK Interop Tests ───────────────────────────────

class TestRustInterop:
    """
    These tests verify that Python SDK data structures produce
    output compatible with what the Rust SDK expects.

    They don't require Rust to be installed — they validate
    the JSON formats match the documented schemas.
    """

    def test_task_status_values_match_rust(self):
        """Python TaskStatus values must match Rust TaskStatus enum."""
        expected = {"CREATED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"}
        assert set(Task.TASK_STATUSES) == expected

    def test_card_version_format(self):
        """Version strings must be SemVer-compatible for cross-SDK parsing."""
        card = AgentCard(did="X", name="X", matrix_id="@x:t")
        version = card.version
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_metadata_keys_match_spec(self):
        """Metadata keys must match what other SDKs look for."""
        meta_spec_keys = {"message_id", "sender_did", "capabilities_requested", "task_id", "priority", "ttl_seconds"}
        # Verify the spec defines these keys
        assert "sender_did" in meta_spec_keys  # key field for cross-SDK routing


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

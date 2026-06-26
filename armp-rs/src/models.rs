//! ARMP data models — AgentCard, Capability, Message, Task, NegotiationResult.

use crate::constants::TaskStatus;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ── Capability ────────────────────────────────────────

/// A single agent capability declaration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capability {
    pub name: String,
    #[serde(default)]
    pub description: String,
}

impl Capability {
    pub fn new(name: impl Into<String>, description: impl Into<String>) -> Self {
        Capability {
            name: name.into(),
            description: description.into(),
        }
    }
}

// ── Agent Card ────────────────────────────────────────

/// An agent's public identity and capability card.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCard {
    pub did: String,
    pub name: String,
    pub matrix_id: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub capabilities: Vec<Capability>,
    #[serde(default)]
    pub endpoints: HashMap<String, String>,
    #[serde(default = "default_version")]
    pub version: String,
}

fn default_version() -> String {
    "0.5.0".to_string()
}

impl AgentCard {
    /// Create a new agent card from the essential fields.
    pub fn new(did: impl Into<String>, name: impl Into<String>, matrix_id: impl Into<String>) -> Self {
        AgentCard {
            did: did.into(),
            name: name.into(),
            matrix_id: matrix_id.into(),
            description: String::new(),
            capabilities: Vec::new(),
            endpoints: HashMap::new(),
            version: "0.5.0".to_string(),
        }
    }

    /// Add a capability to the card.
    pub fn add_capability(&mut self, name: impl Into<String>, description: impl Into<String>) {
        self.capabilities.push(Capability::new(name, description));
    }
}

// ── Message ───────────────────────────────────────────

/// An ARMP message received from another agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub event_id: String,
    pub sender: String,
    pub body: String,
    pub room_id: String,
    pub timestamp: i64,
    #[serde(default = "default_msgtype")]
    pub msgtype: String,
    #[serde(default)]
    pub armp_metadata: Option<ArmpMetadata>,
}

fn default_msgtype() -> String {
    "m.text".to_string()
}

/// Optional ARMP metadata embedded in messages.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ArmpMetadata {
    #[serde(default)]
    pub message_id: String,
    #[serde(default)]
    pub sender_did: String,
    #[serde(default)]
    pub capabilities_requested: Vec<String>,
    pub task_id: Option<String>,
    #[serde(default)]
    pub priority: String,
    pub ttl_seconds: Option<i64>,
}

// ── Task ──────────────────────────────────────────────

/// A task history entry recording a state transition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskHistoryEntry {
    pub from: String,
    pub to: String,
    #[serde(default)]
    pub detail: String,
    pub timestamp: String,
}

/// A task with full lifecycle: CREATED → ASSIGNED → IN_PROGRESS → COMPLETED/FAILED.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub task_id: String,
    pub sender_did: String,
    pub assignee_did: String,
    #[serde(default = "default_task_status")]
    pub status: TaskStatus,
    #[serde(default)]
    pub spec: serde_json::Value,
    pub result: Option<serde_json::Value>,
    #[serde(default)]
    pub progress: f64,
    #[serde(default)]
    pub history: Vec<TaskHistoryEntry>,
}

fn default_task_status() -> TaskStatus {
    TaskStatus::Created
}

impl Task {
    /// Create a new task in CREATED status.
    pub fn new(
        task_id: String,
        sender_did: String,
        assignee_did: String,
        spec: serde_json::Value,
    ) -> Self {
        Task {
            task_id,
            sender_did,
            assignee_did,
            status: TaskStatus::Created,
            spec,
            result: None,
            progress: 0.0,
            history: Vec::new(),
        }
    }

    /// Transition the task to a new status. Returns Ok if valid, Err with the old status otherwise.
    pub fn transition(&mut self, new_status: TaskStatus, detail: &str) -> Result<(), TaskStatus> {
        if !self.status.can_transition_to(new_status) {
            tracing::warn!(
                "Invalid task transition: {} -> {}",
                self.status, new_status
            );
            return Err(self.status);
        }

        let entry = TaskHistoryEntry {
            from: self.status.to_string(),
            to: new_status.to_string(),
            detail: detail.to_string(),
            timestamp: Utc::now().to_rfc3339(),
        };
        self.history.push(entry);
        self.status = new_status;

        tracing::info!("Task {}: {} -> {}", self.task_id, self.status, new_status);
        Ok(())
    }
}

// ── Negotiation Result ───────────────────────────────

/// Result of a capability negotiation between two agents.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NegotiationResult {
    pub peer_did: String,
    pub peer_card: AgentCard,
    pub my_capabilities: Vec<String>,
    pub peer_capabilities: Vec<String>,
    pub mutual_capabilities: Vec<String>,
    pub missing_capabilities: Vec<String>,
    pub matched: bool,
}

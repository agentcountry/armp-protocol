//! ARMP protocol constants — Matrix event types, task statuses, transitions.

use serde::{Deserialize, Serialize};

/// Matrix custom event type for ARMP agent messages.
pub const ARMP_MSG_TYPE: &str = "m.agent.message";

/// Matrix custom event type for ARMP task events.
pub const ARMP_TASK_TYPE: &str = "m.agent.task";

/// Capability negotiation request event type.
pub const ARMP_CAP_REQUEST: &str = "m.agent.capability_request";

/// Capability negotiation response event type.
pub const ARMP_CAP_RESPONSE: &str = "m.agent.capability_response";

/// Account data key for DID binding.
pub const ARMP_ACCOUNT_DATA_DID: &str = "m.agent.did";

/// Protocol version string.
pub const ARMP_VERSION: &str = "0.5.0";

// ── Task Status ────────────────────────────────────────

/// Task lifecycle status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TaskStatus {
    #[serde(rename = "CREATED")]
    Created,
    #[serde(rename = "ASSIGNED")]
    Assigned,
    #[serde(rename = "IN_PROGRESS")]
    InProgress,
    #[serde(rename = "COMPLETED")]
    Completed,
    #[serde(rename = "FAILED")]
    Failed,
    #[serde(rename = "CANCELLED")]
    Cancelled,
}

impl TaskStatus {
    /// Returns the valid transitions from this status.
    pub fn valid_transitions(self) -> &'static [TaskStatus] {
        match self {
            TaskStatus::Created => &[TaskStatus::Assigned, TaskStatus::Cancelled],
            TaskStatus::Assigned => &[TaskStatus::InProgress, TaskStatus::Cancelled],
            TaskStatus::InProgress => &[TaskStatus::Completed, TaskStatus::Failed, TaskStatus::Cancelled],
            TaskStatus::Failed => &[TaskStatus::Assigned], // retry
            TaskStatus::Completed | TaskStatus::Cancelled => &[],
        }
    }

    /// Check if a transition is valid.
    pub fn can_transition_to(self, target: TaskStatus) -> bool {
        self.valid_transitions().contains(&target)
    }
}

impl std::fmt::Display for TaskStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            TaskStatus::Created => "CREATED",
            TaskStatus::Assigned => "ASSIGNED",
            TaskStatus::InProgress => "IN_PROGRESS",
            TaskStatus::Completed => "COMPLETED",
            TaskStatus::Failed => "FAILED",
            TaskStatus::Cancelled => "CANCELLED",
        };
        write!(f, "{}", s)
    }
}

// ── Presence ──────────────────────────────────────────

/// Agent presence/online status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Presence {
    Online,
    Unavailable,
    Offline,
}

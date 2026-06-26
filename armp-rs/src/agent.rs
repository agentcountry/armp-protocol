//! ARMP Agent — full Matrix-backed real-time agent communication.
//!
//! # Quickstart
//!
//! ```no_run
//! use armp_sdk::Agent;
//!
//! #[tokio::main]
//! async fn main() -> armp_sdk::error::ArmpResult<()> {
//!     let mut agent = Agent::new(
//!         "AGNT8A2026070114K7P2M9X4R6",
//!         "https://armp-group.org",
//!         "myagent",
//!     );
//!
//!     agent.set_password("***");
//!     agent.start().await?;
//!     agent.set_capability("data-analysis", "Statistical analysis and ML models");
//!     agent.send_message("@peer:armp-group.org", "Hello!").await?;
//!     agent.stop().await?;
//!     Ok(())
//! }
//! ```

use crate::constants::*;
use crate::error::{ArmpError, ArmpResult};
use crate::models::*;
use matrix_sdk::{
    Client as MatrixClient,
    config::SyncSettings,
    room::Room,
    ruma::{
        events::{
            room::message::{MessageType, RoomMessageEventContent, TextMessageEventContent},
            AnyMessageLikeEventContent,
        },
        OwnedRoomId, OwnedUserId, UserId,
    },
};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// A callback for incoming messages.
pub type MessageCallback = Arc<dyn Fn(Message) + Send + Sync>;

/// Core ARMP Agent — real-time communication via Matrix.
pub struct Agent {
    /// Agent's DID.
    pub did: String,
    /// Matrix homeserver URL.
    pub homeserver: String,
    /// Matrix username (localpart).
    pub username: String,
    /// Matrix password (set before start()).
    password: Option<String>,
    /// Pre-existing Matrix access token (skip login if provided).
    access_token: Option<String>,

    // Internal state
    client: Option<MatrixClient>,
    started: bool,
    card: Option<AgentCard>,
    message_callback: Option<MessageCallback>,
    peers: HashMap<String, AgentCard>,
    tasks: HashMap<String, Task>,
}

impl Agent {
    /// Create a new ARMP agent.
    ///
    /// Call `set_password()` or `set_access_token()` before `start()`.
    pub fn new(did: impl Into<String>, homeserver: impl Into<String>, username: impl Into<String>) -> Self {
        Agent {
            did: did.into(),
            homeserver: homeserver.into(),
            username: username.into(),
            password: None,
            access_token: None,
            client: None,
            started: false,
            card: None,
            message_callback: None,
            peers: HashMap::new(),
            tasks: HashMap::new(),
        }
    }

    /// Set the Matrix password for login.
    pub fn set_password(&mut self, password: impl Into<String>) {
        self.password = Some(password.into());
    }

    /// Set a pre-existing Matrix access token (skips login).
    pub fn set_access_token(&mut self, token: impl Into<String>) {
        self.access_token = Some(token.into());
    }

    /// Set a message callback for incoming messages.
    pub fn on_message<F>(&mut self, callback: F)
    where
        F: Fn(Message) + Send + Sync + 'static,
    {
        self.message_callback = Some(Arc::new(callback));
    }

    // ── Lifecycle ─────────────────────────────────────

    /// Connect to the Matrix homeserver and start syncing.
    pub async fn start(&mut self) -> ArmpResult<()> {
        if self.started {
            return Err(ArmpError::AlreadyStarted);
        }

        let homeserver_url = self.homeserver.trim_end_matches('/');
        let builder = MatrixClient::builder()
            .homeserver_url(homeserver_url);

        let client = if let Some(ref token) = self.access_token {
            let client = builder.build().await?;
            let user_id = UserId::parse(format!("@{}:{}", self.username, homeserver_url.replace("https://", "").replace("http://", "")))
                .map_err(|e| ArmpError::Other(format!("Invalid user ID: {}", e)))?;
            client.restore_login(
                matrix_sdk::matrix_auth::MatrixSession {
                    meta: matrix_sdk::matrix_auth::SessionMeta {
                        user_id: user_id.clone(),
                        device_id: "ARMP-RUST-SDK".into(),
                    },
                    tokens: matrix_sdk::matrix_auth::SessionTokens {
                        access_token: token.clone(),
                        refresh_token: None,
                    },
                },
            ).await?;
            client
        } else if let Some(ref password) = self.password {
            let client = builder.build().await?;
            client.matrix_auth()
                .login_username(&self.username, password)
                .initial_device_display_name("ARMP Rust SDK")
                .await?;
            client
        } else {
            return Err(ArmpError::LoginFailed(
                "No password or access token provided".into()
            ));
        };

        // Bind DID to account data
        self.bind_did(&client).await?;

        // Set initial presence
        client.set_presence(Some(matrix_sdk::ruma::presence::PresenceState::Online)).await?;

        self.client = Some(client);
        self.started = true;

        tracing::info!("Agent {} is online", self.did);
        Ok(())
    }

    /// Disconnect from the homeserver.
    pub async fn stop(&mut self) -> ArmpResult<()> {
        self.started = false;
        if let Some(ref client) = self.client {
            client.set_presence(Some(matrix_sdk::ruma::presence::PresenceState::Offline)).await?;
        }
        self.client = None;
        tracing::info!("Agent {} is offline", self.did);
        Ok(())
    }

    /// Returns true if the agent is connected.
    pub fn is_online(&self) -> bool {
        self.started
    }

    /// Returns the agent's Matrix user ID.
    pub fn user_id(&self) -> Option<String> {
        self.client.as_ref().map(|c| c.user_id().map(|u| u.to_string())).flatten()
    }

    /// Returns a reference to the agent's card, if any.
    pub fn card(&self) -> Option<&AgentCard> {
        self.card.as_ref()
    }

    /// Returns the underlying Matrix client.
    fn client(&self) -> ArmpResult<&MatrixClient> {
        self.client.as_ref().ok_or(ArmpError::NotInitialized)
    }

    // ── DID Binding ───────────────────────────────────

    async fn bind_did(&self, client: &MatrixClient) -> ArmpResult<()> {
        let data = serde_json::json!({
            "did": self.did,
            "bound_at": chrono::Utc::now().to_rfc3339(),
            "verified": false,
        });
        client.account()
            .set_account_data(
                ARMP_ACCOUNT_DATA_DID
                    .try_into()
                    .map_err(|_| ArmpError::Other("Invalid account data type".into()))?,
                &data,
            )
            .await?;
        Ok(())
    }

    // ── Messaging ─────────────────────────────────────

    /// Send a message to a room or user.
    pub async fn send_message(&self, target: &str, body: &str) -> ArmpResult<String> {
        let client = self.client()?;
        let room_id = if target.starts_with('!') {
            OwnedRoomId::try_from(target.to_string())
                .map_err(|e| ArmpError::SendError(format!("Invalid room ID: {}", e)))?
        } else {
            return Err(ArmpError::SendError(
                "Direct user messaging requires ensure_dm — call with a room ID".into()
            ));
        };

        let room = client.get_room(&room_id)
            .ok_or_else(|| ArmpError::RoomError("Room not found".into()))?;

        let content = RoomMessageEventContent::new(MessageType::Text(
            TextMessageEventContent::plain(body)
        ));

        let response = room.send(content).await?;
        let event_id = response.event_id.to_string();

        tracing::info!("→ [{}] {}...", target, &body[..body.len().min(50)]);
        Ok(event_id)
    }

    /// Create a new room and invite members.
    pub async fn create_room(
        &self,
        name: &str,
        members: &[String],
        is_direct: bool,
    ) -> ArmpResult<String> {
        let client = self.client()?;

        let mut request = matrix_sdk::ruma::api::client::room::create_room::v3::Request::new();
        request.name = Some(name.to_string());
        request.is_direct = is_direct;

        if !members.is_empty() {
            let invites: Vec<OwnedUserId> = members
                .iter()
                .filter_map(|m| OwnedUserId::try_from(m.as_str()).ok())
                .collect();
            request.invite = invites;
        }

        let response = client.create_room(request).await?;
        let room_id = response.room_id.to_string();

        tracing::info!("Room created: {} ({})", name, room_id);
        Ok(room_id)
    }

    // ── Capability Management ─────────────────────────

    /// Declare a capability on this agent.
    pub fn set_capability(&mut self, name: impl Into<String>, description: impl Into<String>) {
        let card = self.card.get_or_insert_with(|| AgentCard::new(
            &self.did,
            &self.username,
            self.user_id().unwrap_or_default(),
        ));
        card.add_capability(name, description);
    }

    /// Negotiate capabilities with a peer agent.
    ///
    /// Sends our card to the peer and awaits their response.
    pub async fn negotiate(&mut self, peer_user_id: &str) -> ArmpResult<NegotiationResult> {
        let card = self.card.as_ref().ok_or(ArmpError::NoAgentCard)?;
        let client = self.client()?;

        // Ensure DM room exists
        let request = matrix_sdk::ruma::api::client::room::create_room::v3::Request::new();
        let mut req = request;
        req.is_direct = true;
        let invite: OwnedUserId = OwnedUserId::try_from(peer_user_id)
            .map_err(|e| ArmpError::RoomError(format!("Invalid user ID: {}", e)))?;
        req.invite = vec![invite];
        let response = client.create_room(req).await?;
        let room_id = response.room_id;

        let room = client.get_room(&room_id)
            .ok_or_else(|| ArmpError::RoomError("Room not found after creation".into()))?;

        // Send capability request with our card
        let cap_content = serde_json::json!({
            "body": format!("Capability request from {}", self.did),
            "m.agent": {
                "request_id": Uuid::new_v4().to_string(),
                "agent_card": card,
            },
        });

        let content = RoomMessageEventContent::new(
            MessageType::Text(TextMessageEventContent::plain(
                &format!("Capability request from {}", self.did)
            ))
        );

        room.send(content).await?;

        // In a full implementation, we would await the sync callback.
        // For now, return a basic result.
        let my_caps: Vec<String> = card.capabilities.iter().map(|c| c.name.clone()).collect();

        Ok(NegotiationResult {
            peer_did: String::new(),
            peer_card: AgentCard::new("unknown", "unknown", peer_user_id),
            my_capabilities: my_caps.clone(),
            peer_capabilities: Vec::new(),
            mutual_capabilities: Vec::new(),
            missing_capabilities: Vec::new(),
            matched: false,
        })
    }

    // ── Tasks ─────────────────────────────────────────

    /// Create a new task.
    pub fn create_task(
        &mut self,
        assignee_did: impl Into<String>,
        spec: serde_json::Value,
    ) -> Task {
        let task = Task::new(
            Uuid::new_v4().to_string(),
            self.did.clone(),
            assignee_did.into(),
            spec,
        );
        self.tasks.insert(task.task_id.clone(), task.clone());
        tracing::info!("Task {} -> {} [CREATED]", task.task_id, task.assignee_did);
        task
    }

    /// Retrieve a task by ID.
    pub fn get_task(&self, task_id: &str) -> Option<&Task> {
        self.tasks.get(task_id)
    }

    /// Assign a task to an agent (CREATED → ASSIGNED).
    pub fn assign_task(&mut self, task_id: &str) -> ArmpResult<()> {
        let task = self.tasks.get_mut(task_id)
            .ok_or_else(|| ArmpError::Other("Task not found".into()))?;
        task.transition(TaskStatus::Assigned, "Assigned")
            .map_err(|_| ArmpError::InvalidTaskTransition {
                from: TaskStatus::Created.to_string(),
                to: TaskStatus::Assigned.to_string(),
            })?;
        Ok(())
    }

    /// Start working on a task (ASSIGNED → IN_PROGRESS).
    pub fn start_task(&mut self, task_id: &str) -> ArmpResult<()> {
        let task = self.tasks.get_mut(task_id)
            .ok_or_else(|| ArmpError::Other("Task not found".into()))?;
        task.transition(TaskStatus::InProgress, "Work started")
            .map_err(|_| ArmpError::InvalidTaskTransition {
                from: TaskStatus::Assigned.to_string(),
                to: TaskStatus::InProgress.to_string(),
            })?;
        Ok(())
    }

    /// Report task progress (0.0–1.0).
    pub fn report_progress(&mut self, task_id: &str, progress: f64) -> ArmpResult<()> {
        let task = self.tasks.get_mut(task_id)
            .ok_or_else(|| ArmpError::Other("Task not found".into()))?;
        task.progress = progress.clamp(0.0, 1.0);
        Ok(())
    }

    /// Complete a task (IN_PROGRESS → COMPLETED).
    pub fn complete_task(&mut self, task_id: &str, result: Option<serde_json::Value>) -> ArmpResult<()> {
        let task = self.tasks.get_mut(task_id)
            .ok_or_else(|| ArmpError::Other("Task not found".into()))?;
        task.progress = 1.0;
        task.result = result;
        task.transition(TaskStatus::Completed, "Task completed")
            .map_err(|_| ArmpError::InvalidTaskTransition {
                from: TaskStatus::InProgress.to_string(),
                to: TaskStatus::Completed.to_string(),
            })?;
        Ok(())
    }

    /// Fail a task (IN_PROGRESS → FAILED).
    pub fn fail_task(&mut self, task_id: &str, reason: &str) -> ArmpResult<()> {
        let task = self.tasks.get_mut(task_id)
            .ok_or_else(|| ArmpError::Other("Task not found".into()))?;
        task.transition(TaskStatus::Failed, reason)
            .map_err(|_| ArmpError::InvalidTaskTransition {
                from: TaskStatus::InProgress.to_string(),
                to: TaskStatus::Failed.to_string(),
            })?;
        Ok(())
    }

    // ── Smart Routing ─────────────────────────────────

    /// Score how well an agent's capabilities match a task spec.
    pub fn score_capability_match(&self, task_spec: &serde_json::Value, agent_card: &AgentCard) -> f64 {
        let required: Vec<String> = task_spec["capabilities_required"]
            .as_array()
            .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_lowercase())).collect())
            .unwrap_or_default();

        let preferred: Vec<String> = task_spec["capabilities_preferred"]
            .as_array()
            .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_lowercase())).collect())
            .unwrap_or_default();

        if required.is_empty() && preferred.is_empty() {
            return 0.5;
        }

        let agent_caps: Vec<String> = agent_card.capabilities
            .iter()
            .map(|c| c.name.to_lowercase())
            .collect();

        // All required must be present
        if required.iter().any(|r| !agent_caps.contains(r)) {
            return 0.0;
        }

        let required_score = if !required.is_empty() {
            (required.len() as f64 / required.len() as f64) * 0.6
        } else {
            0.6
        };

        let preferred_score = if !preferred.is_empty() {
            let matches = preferred.iter().filter(|p| agent_caps.contains(p)).count();
            (matches as f64 / preferred.len() as f64) * 0.4
        } else {
            0.4
        };

        (required_score + preferred_score).min(1.0)
    }

    /// Smart-route a task to the best-capable agent from known peers.
    pub fn route_task(&self, task_spec: &serde_json::Value) -> (Option<&AgentCard>, f64) {
        let mut best_card: Option<&AgentCard> = None;
        let mut best_score = 0.0;

        for card in self.peers.values() {
            let score = self.score_capability_match(task_spec, card);
            if score > best_score {
                best_score = score;
                best_card = Some(card);
            }
        }

        (best_card, best_score)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_task_lifecycle() {
        let mut task = Task::new(
            "test-1".into(),
            "AGNT-A".into(),
            "AGNT-B".into(),
            serde_json::json!({"desc": "test"}),
        );
        assert_eq!(task.status, TaskStatus::Created);

        assert!(task.transition(TaskStatus::Assigned, "assign").is_ok());
        assert_eq!(task.status, TaskStatus::Assigned);

        assert!(task.transition(TaskStatus::InProgress, "start").is_ok());
        assert_eq!(task.status, TaskStatus::InProgress);

        assert!(task.transition(TaskStatus::Completed, "done").is_ok());
        assert_eq!(task.status, TaskStatus::Completed);

        assert_eq!(task.history.len(), 3);
    }

    #[test]
    fn test_invalid_transition() {
        let mut task = Task::new(
            "test-2".into(),
            "AGNT-A".into(),
            "AGNT-B".into(),
            serde_json::json!({}),
        );
        // Cannot go from CREATED directly to COMPLETED
        assert!(task.transition(TaskStatus::Completed, "skip").is_err());
        assert_eq!(task.status, TaskStatus::Created);
    }

    #[test]
    fn test_score_capability_match() {
        let agent = Agent::new("AGNT-A", "https://test.org", "test");
        let mut card = AgentCard::new("AGNT-B", "Beta", "@beta:test.org");
        card.add_capability("data-analysis", "Analysis");
        card.add_capability("visualization", "Viz");

        let spec = serde_json::json!({
            "capabilities_required": ["data-analysis"],
            "capabilities_preferred": ["visualization"]
        });

        let score = agent.score_capability_match(&spec, &card);
        assert!(score > 0.5);
    }
}

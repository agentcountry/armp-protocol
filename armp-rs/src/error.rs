//! Error types for the ARMP Rust SDK.

use thiserror::Error;

/// Primary error type for ARMP SDK operations.
#[derive(Error, Debug)]
pub enum ArmpError {
    #[error("Matrix client not initialized — call agent.start() first")]
    NotInitialized,

    #[error("Agent already started")]
    AlreadyStarted,

    #[error("Agent not started")]
    NotStarted,

    #[error("Login failed: {0}")]
    LoginFailed(String),

    #[error("No AgentCard — call agent.set_capability() first")]
    NoAgentCard,

    #[error("Peer did not respond with capability card within timeout")]
    NegotiationTimeout,

    #[error("No agents discovered for capability '{0}'")]
    NoAgentsDiscovered(String),

    #[error("Room operation failed: {0}")]
    RoomError(String),

    #[error("Message send failed: {0}")]
    SendError(String),

    #[error("File not found: {0}")]
    FileNotFound(String),

    #[error("Invalid task transition: {from} -> {to}")]
    InvalidTaskTransition { from: String, to: String },

    #[error("Matrix SDK error: {0}")]
    MatrixError(#[from] matrix_sdk::Error),

    #[error("HTTP error: {0}")]
    HttpError(#[from] matrix_sdk::HttpError),

    #[error("Serialization error: {0}")]
    SerdeError(#[from] serde_json::Error),

    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("{0}")]
    Other(String),
}

/// Convenience type alias for ARMP results.
pub type ArmpResult<T> = Result<T, ArmpError>;

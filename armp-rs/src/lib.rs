//! # ARMP Rust SDK
//!
//! Agent Real-time Message Protocol — real-time communication for AI agents via Matrix.
//!
//! ## Quickstart
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
//!     agent.set_password("***");
//!     agent.start().await?;
//!     agent.set_capability("data-analysis", "Statistical analysis and ML models");
//!     println!("Agent online: {}", agent.is_online());
//!     agent.stop().await?;
//!     Ok(())
//! }
//! ```

pub mod agent;
pub mod constants;
pub mod error;
pub mod models;

pub use agent::Agent;
pub use constants::*;
pub use error::{ArmpError, ArmpResult};
pub use models::*;

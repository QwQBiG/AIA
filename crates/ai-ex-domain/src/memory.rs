use crate::{AppError, conversation::TurnId};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[path = "memory_time.rs"]
mod timestamp;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryKind {
    #[default]
    Conversation,
    Viewer,
    Persona,
    LiveEvent,
}

impl MemoryKind {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Conversation => "conversation",
            Self::Viewer => "viewer",
            Self::Persona => "persona",
            Self::LiveEvent => "live_event",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MemoryProjection {
    pub kind: MemoryKind,
    pub event_id: Uuid,
    pub turn_id: Option<TurnId>,
    pub user_text: String,
    pub assistant_text: String,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemorySource {
    #[default]
    Automatic,
    UserNote,
    UserCorrection,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub id: Uuid,
    #[serde(default = "default_profile")]
    pub profile_id: String,
    pub turn_id: TurnId,
    #[serde(with = "timestamp")]
    pub created_ms: u128,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        with = "timestamp::optional"
    )]
    pub updated_ms: Option<u128>,
    #[serde(default)]
    pub kind: MemoryKind,
    pub user_text: String,
    pub assistant_text: String,
    #[serde(default)]
    pub source: MemorySource,
    #[serde(default = "initial_revision")]
    pub revision: u64,
}

fn default_profile() -> String {
    "default".to_owned()
}

fn initial_revision() -> u64 {
    1
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum MemoryRequest {
    List {
        profile_id: String,
        query: String,
        kind: Option<MemoryKind>,
        offset: usize,
        limit: usize,
    },
    Remember {
        profile_id: String,
        text: String,
    },
    Correct {
        profile_id: String,
        id: Uuid,
        expected_revision: u64,
        text: String,
    },
    Forget {
        profile_id: String,
        id: Uuid,
        expected_revision: u64,
    },
}

impl MemoryRequest {
    pub fn profile_id(&self) -> &str {
        match self {
            Self::List { profile_id, .. }
            | Self::Remember { profile_id, .. }
            | Self::Correct { profile_id, .. }
            | Self::Forget { profile_id, .. } => profile_id,
        }
    }

    pub fn is_mutation(&self) -> bool {
        !matches!(self, Self::List { .. })
    }

    pub fn validate(&self) -> Result<(), AppError> {
        if self.profile_id().trim().is_empty() || self.profile_id().chars().count() > 128 {
            return Err(AppError::configuration(
                "memory profile ID is outside supported bounds",
            ));
        }
        match self {
            Self::List {
                query,
                limit,
                offset,
                ..
            } => {
                if query.chars().count() > 512
                    || !(1..=100).contains(limit)
                    || offset.checked_add(*limit).is_none()
                {
                    return Err(AppError::configuration(
                        "memory query or page is outside supported bounds",
                    ));
                }
            }
            Self::Remember { text, .. } | Self::Correct { text, .. } => {
                if text.trim().is_empty() || text.chars().count() > 4096 {
                    return Err(AppError::configuration(
                        "memory text must contain between 1 and 4096 characters",
                    ));
                }
            }
            Self::Forget { .. } => {}
        }
        if matches!(
            self,
            Self::Correct {
                expected_revision: 0,
                ..
            } | Self::Forget {
                expected_revision: 0,
                ..
            }
        ) {
            return Err(AppError::configuration("memory revision must be positive"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MemoryPage {
    pub profile_id: String,
    pub enabled: bool,
    pub total: usize,
    pub offset: usize,
    pub entries: Vec<MemoryEntry>,
    #[serde(default)]
    pub truncated_ids: Vec<Uuid>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", content = "data", rename_all = "snake_case")]
pub enum MemoryResponse {
    Page(MemoryPage),
    Changed,
}

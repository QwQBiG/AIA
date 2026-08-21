use crate::conversation::TurnId;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryKind
{
    #[default]
    Conversation,
    Viewer,
    Persona,
    LiveEvent,
}

impl MemoryKind
{
    pub const fn as_str(self) -> &'static str
    {
        match self
        {
            Self::Conversation => "conversation",
            Self::Viewer => "viewer",
            Self::Persona => "persona",
            Self::LiveEvent => "live_event",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MemoryProjection
{
    pub kind: MemoryKind,
    pub event_id: Uuid,
    pub turn_id: Option<TurnId>,
    pub user_text: String,
    pub assistant_text: String,
}
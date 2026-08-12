use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct TurnId(pub Uuid);

impl TurnId
{
    pub fn new() -> Self
    {
        Self(Uuid::new_v4())
    }
}

impl Default for TurnId
{
    fn default() -> Self
    {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConversationState
{
    Idle,
    Listening,
    Thinking,
    Speaking,
    Interrupted,
    Failed,
    Stopped,
}

impl ConversationState
{
    pub fn accepts_input(self) -> bool
    {
        matches!(self, Self::Idle | Self::Listening | Self::Interrupted)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role
{
    System,
    User,
    Assistant,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Emotion
{
    Neutral,
    Happy,
    Angry,
    Sad,
    Surprised,
}

impl Emotion
{
    pub fn parse(value: &str) -> Option<Self>
    {
        match value.trim().to_ascii_lowercase().as_str()
        {
            "neutral" => Some(Self::Neutral),
            "happy" => Some(Self::Happy),
            "angry" => Some(Self::Angry),
            "sad" => Some(Self::Sad),
            "surprised" => Some(Self::Surprised),
            _ => None,
        }
    }

    pub const fn as_str(self) -> &'static str
    {
        match self
        {
            Self::Neutral => "neutral",
            Self::Happy => "happy",
            Self::Angry => "angry",
            Self::Sad => "sad",
            Self::Surprised => "surprised",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Message
{
    pub role: Role,
    pub content: String,
}

impl Message
{
    pub fn new(role: Role, content: impl Into<String>) -> Self
    {
        Self {
            role,
            content: content.into(),
        }
    }
}

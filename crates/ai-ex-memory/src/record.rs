use std::collections::BTreeSet;

use ai_ex_domain::TurnId;
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
    pub fn as_str(self) -> &'static str
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord
{
    pub id: Uuid,
    pub turn_id: TurnId,
    pub created_ms: u128,
    #[serde(default)]
    pub kind: MemoryKind,
    pub user_text: String,
    pub assistant_text: String,
}

impl MemoryRecord
{
    pub fn searchable_text(&self) -> String
    {
        format!("{} {}", self.user_text, self.assistant_text)
    }

    pub fn relevance(&self, query: &str) -> usize
    {
        let query_terms = terms(query);
        let document_terms = terms(&self.searchable_text());
        query_terms.intersection(&document_terms).count()
    }
}

fn terms(text: &str) -> BTreeSet<String>
{
    let lowercase = text.to_lowercase();
    let mut result: BTreeSet<String> = lowercase
        .split(|character: char| !character.is_alphanumeric())
        .filter(|term| !term.is_empty())
        .map(str::to_owned)
        .collect();
    for character in lowercase.chars().filter(|character| !character.is_whitespace())
    {
        if !character.is_ascii_punctuation()
        {
            result.insert(character.to_string());
        }
    }
    result
}

use std::collections::BTreeMap;

use ai_ex_domain::{AppError, ConversationState, Emotion};
use serde::{Deserialize, Serialize};

#[path = "appearance_files.rs"]
mod files;
pub use files::LoadedAppearance;

#[cfg(test)]
#[path = "appearance_tests.rs"]
mod tests;

pub const APPEARANCE_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AppearanceManifest
{
    pub schema_version: u16,
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub license: String,
    pub images: BTreeMap<String, String>,
}

impl AppearanceManifest
{
    pub fn parse(text: &str) -> Result<Self, AppError>
    {
        if text.len() > 65_536
        {
            return Err(AppError::configuration("appearance manifest exceeds 64 KiB"));
        }
        let manifest: Self = toml::from_str(text)
            .map_err(|error| AppError::configuration(format!("invalid appearance manifest: {error}")))?;
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.schema_version != APPEARANCE_SCHEMA_VERSION
        {
            return Err(AppError::configuration("unsupported appearance schema_version; expected 1"));
        }
        if self.id.is_empty() || self.id.len() > 128
            || !self.id.bytes().all(|byte| byte.is_ascii_alphanumeric() || b"._-".contains(&byte))
            || self.name.trim().is_empty() || self.name.chars().count() > 128
            || self.author.chars().count() > 512 || self.license.chars().count() > 1024
        {
            return Err(AppError::configuration("appearance identity is outside supported bounds"));
        }
        if !self.images.contains_key("default") || self.images.len() > 24
        {
            return Err(AppError::configuration("appearance requires a default image and at most 24 frames"));
        }
        for (key, path) in &self.images
        {
            let known = matches!(key.as_str(), "default" | "listening" | "thinking" | "speaking" | "blink")
                || ["happy", "sad", "angry", "surprised"].iter().any(|emotion|
                    key == emotion || key == &format!("{emotion}_speaking") || key == &format!("{emotion}_blink"));
            if !known
            {
                return Err(AppError::configuration(format!("unsupported appearance image key: {key}")));
            }
            if path.len() > 512 || path.contains(['\\', ':', '\0'])
                || path.split('/').any(|part| part.is_empty() || part == "." || part == "..")
                || ![".png", ".jpg", ".jpeg"].iter().any(|extension| path.to_ascii_lowercase().ends_with(extension))
            {
                return Err(AppError::configuration(format!("image {key} requires a relative PNG/JPEG path using forward slashes")));
            }
        }
        Ok(())
    }

    pub fn frame_key(&self, activity: ConversationState, emotion: Emotion, mouth_open: bool, blink: bool) -> &str
    {
        if matches!(activity, ConversationState::Interrupted | ConversationState::Stopped | ConversationState::Failed)
        {
            return "default";
        }
        let emotion = match emotion
        {
            Emotion::Neutral => "default", Emotion::Happy => "happy", Emotion::Sad => "sad",
            Emotion::Angry => "angry", Emotion::Surprised => "surprised",
        };
        let mut candidates = Vec::with_capacity(5);
        if activity == ConversationState::Speaking && mouth_open
        {
            candidates.push(format!("{emotion}_speaking"));
            candidates.push("speaking".to_owned());
        }
        else if blink
        {
            candidates.push(format!("{emotion}_blink"));
            candidates.push("blink".to_owned());
        }
        if matches!(activity, ConversationState::Listening | ConversationState::Thinking)
        {
            candidates.push(if activity == ConversationState::Listening { "listening" } else { "thinking" }.to_owned());
        }
        candidates.push(emotion.to_owned());
        for key in candidates
        {
            if let Some((key, _)) = self.images.get_key_value(&key)
            {
                return key;
            }
        }
        "default"
    }
}

use serde::{Deserialize, Serialize};

use crate::{Emotion, TurnId};

/// Output-device playback position and a normalized PCM energy measurement.
/// This is not a phoneme/viseme classification or microphone measurement.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SpeechPlaybackSnapshot {
    pub turn_id: Option<TurnId>,
    pub active: bool,
    /// RMS-derived mouth opening, in the inclusive range 0..=1000.
    pub mouth_level: u16,
    pub position_ms: u64,
    pub duration_ms: u64,
    /// Stable identity for this sentence, including repeated identical text.
    #[serde(default)]
    pub sentence_id: Option<uuid::Uuid>,
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub emotion: Option<Emotion>,
}

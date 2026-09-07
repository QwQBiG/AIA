use std::sync::atomic::{AtomicBool, Ordering};

use ai_ex_domain::{SpeechPlaybackSnapshot, SystemEvent};
use ai_ex_observability::EventHub;

pub struct PlaybackPublisher {
    events: EventHub,
    started: AtomicBool,
}

impl PlaybackPublisher {
    pub fn new(events: EventHub) -> Self {
        Self {
            events,
            started: AtomicBool::new(false),
        }
    }

    pub fn observe(&self, playback: SpeechPlaybackSnapshot) {
        let progress = playback.active && self.started.swap(true, Ordering::AcqRel);
        let event = if progress && let Some(sentence_id) = playback.sentence_id {
            SystemEvent::SpeechProgress {
                sentence_id,
                position_ms: playback.position_ms,
                mouth_level: playback.mouth_level,
            }
        } else {
            SystemEvent::SpeechPlayback { playback }
        };
        self.events.publish_now(event);
    }
}

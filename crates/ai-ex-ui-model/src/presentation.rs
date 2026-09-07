use ai_ex_domain::{ConversationState, Emotion};
use serde::{Deserialize, Serialize};

use crate::{ConnectionState, UiState};

#[cfg(test)]
#[path = "speech_tests.rs"]
mod speech_tests;

/// Renderer-independent expression. It describes presentation, not consciousness
/// or measured audio amplitude. Renderers may implement only part of this state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct PresentationState {
    pub connected: bool,
    pub synchronized: bool,
    pub activity: ConversationState,
    pub emotion: Emotion,
    /// Some(level) uses measured playback. None is reserved for offline demos.
    #[serde(default)]
    pub mouth_level: Option<u16>,
}

impl PresentationState {
    pub fn from_ui(ui: &UiState) -> Self {
        let connected = ui.connection == ConnectionState::Connected;
        let synchronized = connected && !ui.needs_resync;
        let mut activity = if synchronized {
            ui.runtime.state
        } else {
            ConversationState::Idle
        };
        let playback_allowed = synchronized
            && !ui.runtime.speech_cancelled
            && !matches!(
                activity,
                ConversationState::Stopped
                    | ConversationState::Failed
                    | ConversationState::Interrupted
                    | ConversationState::Listening,
            );
        let playing = playback_allowed && ui.runtime.playback.active;
        if playing {
            activity = ConversationState::Speaking;
        }
        let expressive = synchronized
            && !matches!(
                activity,
                ConversationState::Stopped
                    | ConversationState::Failed
                    | ConversationState::Interrupted,
            );
        Self {
            connected,
            synchronized,
            activity,
            emotion: if playing {
                ui.runtime.playback.emotion.unwrap_or(Emotion::Neutral)
            } else if expressive {
                ui.runtime.current_emotion.unwrap_or(Emotion::Neutral)
            } else {
                Emotion::Neutral
            },
            mouth_level: Some(if playing {
                ui.runtime.playback.mouth_level.min(1000)
            } else {
                0
            }),
        }
    }

    pub fn subtitle(ui: &UiState) -> Option<&str> {
        let presentation = Self::from_ui(ui);
        (presentation.connected
            && presentation.synchronized
            && !ui.runtime.speech_cancelled
            && presentation.activity == ConversationState::Speaking
            && ui.runtime.playback.active
            && !ui.runtime.playback.text.is_empty())
        .then_some(ui.runtime.playback.text.as_str())
    }

    pub fn label(self) -> &'static str {
        if !self.connected {
            return "离线";
        }
        if !self.synchronized {
            return "同步中";
        }
        match self.activity {
            ConversationState::Idle => "陪伴中",
            ConversationState::Listening => "倾听中",
            ConversationState::Thinking => "思考中",
            ConversationState::Speaking => "表达中",
            ConversationState::Interrupted => "已暂停表达",
            ConversationState::Failed => "需要处理故障",
            ConversationState::Stopped => "已停止",
        }
    }

    pub fn animate(self, elapsed_seconds: f64, reduced_motion: bool) -> AnimationFrame {
        let active = self.connected
            && self.synchronized
            && !matches!(
                self.activity,
                ConversationState::Stopped
                    | ConversationState::Failed
                    | ConversationState::Interrupted,
            );
        if !active || reduced_motion || !elapsed_seconds.is_finite() {
            return AnimationFrame {
                breath: 0.0,
                eyes_open: 1.0,
                mouth_open: 0.0,
                gaze_x: 0.0,
            };
        }
        let time = elapsed_seconds.rem_euclid(120.0) as f32;
        let blink = time.rem_euclid(4.7);
        AnimationFrame {
            breath: (time * 1.6).sin(),
            eyes_open: if blink < 0.16 {
                (blink / 0.08 - 1.0).abs()
            } else {
                1.0
            },
            mouth_open: self
                .mouth_level
                .map(|level| level.min(1000) as f32 / 1000.0)
                .unwrap_or_else(|| {
                    if self.activity == ConversationState::Speaking {
                        0.2 + 0.6 * (time * 9.0).sin().abs()
                    } else {
                        0.0
                    }
                }),
            gaze_x: if self.activity == ConversationState::Thinking {
                0.6
            } else {
                (time * 0.4).sin() * 0.18
            },
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AnimationFrame {
    pub breath: f32,
    pub eyes_open: f32,
    pub mouth_open: f32,
    pub gaze_x: f32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disconnect_and_event_gap_do_not_keep_a_stale_expression_alive() {
        let mut ui = UiState::new(10).unwrap();
        ui.runtime.state = ConversationState::Speaking;
        ui.runtime.current_emotion = Some(Emotion::Happy);
        let offline = PresentationState::from_ui(&ui);
        assert_eq!(offline.emotion, Emotion::Neutral);
        assert_eq!(offline.animate(1.0, false).mouth_open, 0.0);
        ui.connection = ConnectionState::Connected;
        assert_eq!(PresentationState::from_ui(&ui).emotion, Emotion::Happy);
        ui.needs_resync = true;
        assert_eq!(PresentationState::from_ui(&ui).label(), "同步中");
        assert_eq!(
            PresentationState::from_ui(&ui)
                .animate(1.0, false)
                .mouth_open,
            0.0
        );
    }

    #[test]
    fn animation_is_bounded_and_stops_for_interrupt_or_reduced_motion() {
        let mut state = PresentationState {
            connected: true,
            synchronized: true,
            activity: ConversationState::Speaking,
            emotion: Emotion::Happy,
            mouth_level: None,
        };
        for time in [-1.0, 0.0, 0.08, 1.0, 5000.0, f64::NAN, f64::INFINITY] {
            let frame = state.animate(time, false);
            assert!((0.0..=1.0).contains(&frame.mouth_open));
            assert!((0.0..=1.0).contains(&frame.eyes_open));
        }
        assert_eq!(state.animate(1.0, true).mouth_open, 0.0);
        state.activity = ConversationState::Interrupted;
        assert_eq!(state.animate(1.0, false).mouth_open, 0.0);
    }

    #[test]
    fn model_completion_does_not_end_playback_but_silence_and_interrupt_close_the_mouth() {
        use ai_ex_domain::{SpeechPlaybackSnapshot, SystemEvent, TurnId};
        use ai_ex_observability::SequencedEvent;
        let mut ui = UiState::new(10).unwrap();
        ui.connection = ConnectionState::Connected;
        let turn_id = TurnId::new();
        let playback = SpeechPlaybackSnapshot {
            turn_id: Some(turn_id),
            active: true,
            mouth_level: 750,
            position_ms: 40,
            duration_ms: 1000,
            ..Default::default()
        };
        for (index, event) in [
            SystemEvent::TurnStarted {
                turn_id,
                user_text: "hello".to_owned(),
            },
            SystemEvent::SpeechPlayback { playback },
            SystemEvent::TurnFinished {
                turn_id,
                full_text: "hello back".to_owned(),
            },
        ]
        .into_iter()
        .enumerate()
        {
            ui.apply_event(SequencedEvent {
                sequence: index as u64 + 1,
                event,
            });
        }
        assert_eq!(
            PresentationState::from_ui(&ui).activity,
            ConversationState::Speaking
        );
        assert_eq!(
            PresentationState::from_ui(&ui)
                .animate(1.0, false)
                .mouth_open,
            0.75
        );
        ui.runtime.playback.mouth_level = 0;
        assert_eq!(
            PresentationState::from_ui(&ui)
                .animate(1.0, false)
                .mouth_open,
            0.0
        );
        ui.runtime.playback.mouth_level = 750;
        ui.runtime.state = ConversationState::Interrupted;
        assert_eq!(
            PresentationState::from_ui(&ui)
                .animate(1.0, false)
                .mouth_open,
            0.0
        );
        ui.runtime.state = ConversationState::Speaking;
        ui.runtime.playback = SpeechPlaybackSnapshot::default();
        assert_eq!(
            PresentationState::from_ui(&ui)
                .animate(1.0, false)
                .mouth_open,
            0.0
        );
    }
}

use super::*;
use ai_ex_domain::{SpeechPlaybackSnapshot, SystemEvent, TurnId};
use ai_ex_observability::EventHub;

#[test]
fn sentence_timeline_replays_resynchronizes_and_rejects_cancelled_or_previous_speech()
{
    let hub = EventHub::new(64).unwrap();
    let turn_id = TurnId::new();
    let sentence_id = TurnId::new().0;
    let mut ui = UiState::new(8).unwrap();
    ui.connection = ConnectionState::Connected;
    let mut apply = |event|
    {
        hub.publish_now(event);
        for item in hub.events_since(ui.runtime.last_sequence, 64)
        {
            ui.apply_event(item);
        }
        assert_eq!(ui.runtime, hub.current());
    };
    apply(SystemEvent::TurnStarted { turn_id, user_text: "hi".to_owned() });
    apply(SystemEvent::EmotionChanged { turn_id, emotion: Emotion::Sad });
    apply(SystemEvent::TurnFinished { turn_id, full_text: "Hello.".to_owned() });
    let playing = SpeechPlaybackSnapshot {
        turn_id: Some(turn_id), sentence_id: Some(sentence_id), active: true,
        text: "Hello.".to_owned(), emotion: Some(Emotion::Happy),
        position_ms: 0, duration_ms: 1000, mouth_level: 700,
    };
    apply(SystemEvent::SpeechPlayback { playback: playing.clone() });
    apply(SystemEvent::SpeechProgress { sentence_id, position_ms: 400, mouth_level: 500 });
    assert_eq!(PresentationState::from_ui(&ui).emotion, Emotion::Happy);
    assert_eq!(PresentationState::subtitle(&ui), Some("Hello."));
    assert_eq!(PresentationState::from_ui(&ui).animate(1.0, false).mouth_open, 0.5);
    ui.needs_resync = true;
    assert_eq!(PresentationState::subtitle(&ui), None);
    ui.apply_snapshot(hub.current());
    assert_eq!(PresentationState::subtitle(&ui), Some("Hello."));
    ui.connection = ConnectionState::Disconnected;
    assert_eq!(PresentationState::subtitle(&ui), None);
    ui.connection = ConnectionState::Connected;
    hub.publish_now(SystemEvent::SpeechCancelled);
    hub.publish_now(SystemEvent::SpeechPlayback { playback: playing.clone() });
    hub.publish_now(SystemEvent::SpeechProgress { sentence_id, position_ms: 800, mouth_level: 900 });
    for item in hub.events_since(ui.runtime.last_sequence, 64)
    {
        ui.apply_event(item);
    }
    assert_eq!(ui.runtime, hub.current());
    assert_eq!(PresentationState::subtitle(&ui), None);
    assert_eq!(PresentationState::from_ui(&ui).emotion, Emotion::Neutral);
    let next = TurnId::new();
    hub.publish_now(SystemEvent::TurnStarted { turn_id: next, user_text: "next".to_owned() });
    hub.publish_now(SystemEvent::SpeechPlayback { playback: playing });
    ui.apply_snapshot(hub.current());
    assert_eq!(PresentationState::subtitle(&ui), None);
}

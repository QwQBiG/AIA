use super::*;
use ai_ex_domain::ConversationState;

fn speaking(emotion: Emotion, mouth_level: u16) -> PresentationState {
    PresentationState {
        connected: true,
        synchronized: true,
        activity: ConversationState::Speaking,
        emotion,
        mouth_level: Some(mouth_level),
    }
}

#[test]
fn expression_and_gaze_transition_without_jumping_to_new_state() {
    let mut animator = PresentationAnimator::default();
    let mut state = speaking(Emotion::Neutral, 0);
    state.activity = ConversationState::Idle;
    let before = animator.sample(state, 1.0, false);
    state.activity = ConversationState::Thinking;
    state.emotion = Emotion::Sad;
    let first = animator.sample(state, 1.016, false);
    assert!(first.gaze_x > before.gaze_x && first.gaze_x < 0.6);
    assert!(first.expression.brow_slant > 0.0 && first.expression.brow_slant < 0.1);
    for frame in 2..=60 {
        animator.sample(state, 1.0 + f64::from(frame) / 60.0, false);
    }
    let settled = animator.sample(state, 2.0, false);
    assert!((settled.gaze_x - 0.6).abs() < 0.001);
    assert!((settled.expression.brow_slant - 1.0).abs() < 0.005);
    state.activity = ConversationState::Speaking;
    state.emotion = Emotion::Happy;
    state.mouth_level = Some(900);
    let speaking = animator.sample(state, 2.016, false);
    assert!(speaking.gaze_x > 0.5 && speaking.gaze_x < settled.gaze_x);
    assert!(speaking.mouth_open > 0.0 && speaking.mouth_open < 0.5);
    assert!(speaking.expression.brow_slant > 0.8);
    assert!(speaking.expression.blush > 0.0 && speaking.expression.blush < 0.1);
}

#[test]
fn every_stop_condition_closes_the_mouth_even_without_elapsed_time() {
    for case in 0..9 {
        let mut animator = PresentationAnimator::default();
        let mut state = speaking(Emotion::Surprised, 900);
        assert_eq!(animator.sample(state, 1.0, false).mouth_open, 0.9);
        match case {
            0 => state.connected = false,
            1 => state.synchronized = false,
            2 => state.activity = ConversationState::Interrupted,
            3 => state.activity = ConversationState::Stopped,
            4 => state.activity = ConversationState::Failed,
            5 => state.activity = ConversationState::Listening,
            6 => state.activity = ConversationState::Idle,
            7 => state.mouth_level = Some(0),
            8 => (),
            _ => unreachable!(),
        }
        assert_eq!(animator.sample(state, 1.0, case == 8).mouth_open, 0.0);
        state = speaking(Emotion::Happy, 800);
        let resumed = animator.sample(state, 1.016, false);
        assert!(resumed.mouth_open > 0.0 && resumed.mouth_open < 0.4);
    }
}

#[test]
fn smoothing_is_independent_of_refresh_rate_and_discards_hidden_view_history() {
    let run = |fps: u32| {
        let mut animator = PresentationAnimator::default();
        animator.sample(speaking(Emotion::Neutral, 0), 0.0, false);
        let mut frame = None;
        for tick in 1..=fps {
            frame = Some(animator.sample(
                speaking(Emotion::Happy, 800),
                f64::from(tick) / f64::from(fps),
                false,
            ));
        }
        frame.unwrap()
    };
    let slow = run(30);
    let fast = run(120);
    assert!((slow.expression.blush - fast.expression.blush).abs() < 0.00001);
    assert!((slow.mouth_open - fast.mouth_open).abs() < 0.00001);
    let mut animator = PresentationAnimator::default();
    animator.sample(speaking(Emotion::Angry, 900), 1.0, false);
    let fresh = speaking(Emotion::Happy, 200);
    assert_eq!(
        animator.sample(fresh, 10.0, false),
        fresh.animate(10.0, false)
    );
    assert_eq!(
        animator.sample(fresh, 2.0, false),
        fresh.animate(2.0, false)
    );
    for time in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(animator.sample(fresh, time, false).mouth_open, 0.0);
    }
}

#[test]
fn long_running_idle_animation_has_no_periodic_clock_reset_jump() {
    let mut state = speaking(Emotion::Neutral, 0);
    state.activity = ConversationState::Idle;
    let before = state.animate(119.999, false);
    let after = state.animate(120.001, false);
    assert!((before.breath - after.breath).abs() < 0.01);
    assert!((before.gaze_x - after.gaze_x).abs() < 0.01);
    assert!((before.eyes_open - after.eyes_open).abs() < 0.01);
    for time in [-f64::MAX, f64::MAX] {
        let frame = state.animate(time, false);
        assert!(frame.breath.is_finite() && frame.gaze_x.is_finite());
        assert!((0.0..=1.0).contains(&frame.eyes_open));
    }
}

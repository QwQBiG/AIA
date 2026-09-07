use super::{AnimationFrame, Emotion, PresentationState};

/// Continuous facial controls, independent of a particular body or renderer.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ExpressionFrame {
    pub brow_slant: f32,
    pub brow_raise: f32,
    pub eye_widen: f32,
    pub mouth_curve: f32,
    pub blush: f32,
}

impl ExpressionFrame {
    pub fn from_emotion(emotion: Emotion) -> Self {
        Self {
            brow_slant: match emotion {
                Emotion::Angry => -1.0,
                Emotion::Sad => 1.0,
                _ => 0.0,
            },
            brow_raise: f32::from(emotion == Emotion::Surprised),
            eye_widen: f32::from(emotion == Emotion::Surprised),
            mouth_curve: match emotion {
                Emotion::Happy => 1.0,
                Emotion::Sad | Emotion::Angry => -0.57,
                Emotion::Surprised => 0.0,
                Emotion::Neutral => 0.43,
            },
            blush: f32::from(emotion == Emotion::Happy),
        }
    }

    fn blend(self, target: Self, alpha: f32) -> Self {
        Self {
            brow_slant: blend(self.brow_slant, target.brow_slant, alpha),
            brow_raise: blend(self.brow_raise, target.brow_raise, alpha),
            eye_widen: blend(self.eye_widen, target.eye_widen, alpha),
            mouth_curve: blend(self.mouth_curve, target.mouth_curve, alpha),
            blush: blend(self.blush, target.blush, alpha),
        }
    }
}

/// Smooth renderer state across observations without changing runtime events.
/// Each appearance owns one animator; its history is never persisted.
#[derive(Debug, Default)]
pub struct PresentationAnimator {
    previous: Option<(f64, AnimationFrame)>,
}

impl PresentationAnimator {
    pub fn sample(
        &mut self,
        state: PresentationState,
        elapsed_seconds: f64,
        reduced_motion: bool,
    ) -> AnimationFrame {
        let mut target = state.animate(elapsed_seconds, reduced_motion);
        if !elapsed_seconds.is_finite() {
            self.previous = None;
            return target;
        }
        if state.motion_allowed()
            && !reduced_motion
            && let Some((last_time, last)) = self.previous
        {
            let delta = elapsed_seconds - last_time;
            // A hidden view or clock reset must not resume an obsolete transition.
            if (0.0..=0.5).contains(&delta) {
                let alpha = |duration: f32| 1.0 - (-(delta as f32) / duration).exp();
                target.expression = last.expression.blend(target.expression, alpha(0.18));
                target.gaze_x = blend(last.gaze_x, target.gaze_x, alpha(0.12));
                target.breath = blend(last.breath, target.breath, alpha(0.06));
                // Silence and every stop condition close immediately. Never decay
                // an old syllable through a pause, disconnect or interruption.
                if target.mouth_open > 0.0 {
                    target.mouth_open = blend(last.mouth_open, target.mouth_open, alpha(0.035));
                }
            }
        }
        self.previous = Some((elapsed_seconds, target));
        target
    }
}

fn blend(current: f32, target: f32, alpha: f32) -> f32 {
    current + (target - current) * alpha
}

#[cfg(test)]
#[path = "presentation_motion_tests.rs"]
mod tests;

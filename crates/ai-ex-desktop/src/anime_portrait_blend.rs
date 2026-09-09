use super::PortraitFrame;

pub(super) const FACES: [PortraitFrame; 6] = [
    PortraitFrame::Idle,
    PortraitFrame::Thinking,
    PortraitFrame::Happy,
    PortraitFrame::Sad,
    PortraitFrame::Angry,
    PortraitFrame::Surprised,
];

#[derive(Default)]
pub(super) struct FaceBlend {
    previous: Option<(f64, [f32; 8])>,
}

impl FaceBlend {
    pub(super) fn sample(&mut self, target: PortraitFrame, time: f64, still: bool) -> [f32; 8] {
        debug_assert!(FACES.contains(&target));
        let mut weights = [0.0; 8];
        weights[target as usize] = 1.0;
        if !time.is_finite() {
            self.previous = None;
            return weights;
        }
        if !still && let Some((last_time, previous)) = self.previous {
            let delta = time - last_time;
            if (0.0..=0.5).contains(&delta) {
                let alpha = 1.0 - (-(delta as f32) / 0.14).exp();
                for face in FACES {
                    let index = face as usize;
                    weights[index] = previous[index] + (weights[index] - previous[index]) * alpha;
                    if weights[index] < 0.001 {
                        weights[index] = 0.0;
                    }
                }
                let total: f32 = weights.iter().sum();
                for weight in &mut weights {
                    *weight /= total;
                }
            }
        }
        self.previous = Some((time, weights));
        weights
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn changing_emotion_blends_closed_faces_and_a_second_change_remains_continuous() {
        let mut blend = FaceBlend::default();
        blend.sample(PortraitFrame::Happy, 1.0, false);
        let next = blend.sample(PortraitFrame::Sad, 1.03, false);
        assert!(next[PortraitFrame::Happy as usize] > 0.5);
        assert!(next[PortraitFrame::Sad as usize] > 0.0);
        let retargeted = blend.sample(PortraitFrame::Angry, 1.04, false);
        assert!(retargeted[PortraitFrame::Happy as usize] > 0.5);
        assert!(retargeted[PortraitFrame::Sad as usize] > 0.0);
        assert!(retargeted[PortraitFrame::Angry as usize] > 0.0);
        assert!((retargeted.iter().sum::<f32>() - 1.0).abs() < 0.0001);
        assert_eq!(retargeted[PortraitFrame::Speaking as usize], 0.0);
        assert_eq!(retargeted[PortraitFrame::Blink as usize], 0.0);
    }

    #[test]
    fn stopping_or_returning_after_a_hidden_view_discards_the_old_transition() {
        for (time, still) in [(1.03, true), (10.0, false), (0.0, false), (f64::NAN, false)] {
            let mut blend = FaceBlend::default();
            blend.sample(PortraitFrame::Angry, 1.0, false);
            let weights = blend.sample(PortraitFrame::Idle, time, still);
            assert_eq!(weights[PortraitFrame::Idle as usize], 1.0);
            assert_eq!(weights[PortraitFrame::Angry as usize], 0.0);
        }
    }
}

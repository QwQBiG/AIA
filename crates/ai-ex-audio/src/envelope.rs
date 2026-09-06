use ai_ex_domain::AppError;

pub struct SpeechEnvelope
{
    levels: Vec<u16>,
    sample_rate: u32,
    window_frames: u32,
    pub duration_ms: u64,
}

impl SpeechEnvelope
{
    pub fn from_samples(samples: &[f32], channels: u16, sample_rate: u32) -> Result<Self, AppError>
    {
        if channels == 0 || channels > 8 || sample_rate == 0 || sample_rate > 192_000
            || samples.is_empty() || samples.len() % channels as usize != 0
        {
            return Err(AppError::protocol("invalid speech PCM format or incomplete frame"));
        }
        if samples.iter().any(|sample| !sample.is_finite())
        {
            return Err(AppError::protocol("speech PCM contains a non-finite sample"));
        }
        let window_frames = (sample_rate / 25).max(1);
        let window_samples = window_frames as usize * channels as usize;
        let levels = samples.chunks(window_samples).map(|window|
        {
            // Squaring channels independently preserves anti-phase stereo energy.
            let power = window.iter().map(|value| f64::from(value.clamp(-1.0, 1.0)).powi(2)).sum::<f64>() / window.len() as f64;
            let rms = power.sqrt();
            if rms <= 0.01 { 0 } else { (rms * 4.0 * 1000.0).min(1000.0) as u16 }
        }).collect();
        Ok(Self {
            levels,
            sample_rate,
            window_frames,
            duration_ms: (samples.len() / channels as usize) as u64 * 1000 / sample_rate as u64,
        })
    }

    pub fn level_at(&self, position_ms: u64) -> u16
    {
        let frame = position_ms.saturating_mul(self.sample_rate as u64) / 1000;
        let index = frame / self.window_frames as u64;
        usize::try_from(index).ok().and_then(|index| self.levels.get(index)).copied().unwrap_or(0)
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn follows_silence_voice_and_silence_at_playback_position()
    {
        let mut pcm = vec![0.0; 40];
        pcm.extend([0.2; 40]);
        pcm.extend([0.0; 40]);
        let envelope = SpeechEnvelope::from_samples(&pcm, 1, 1000).unwrap();
        assert_eq!(envelope.duration_ms, 120);
        assert_eq!(envelope.level_at(39), 0);
        assert!(envelope.level_at(40) >= 799);
        assert_eq!(envelope.level_at(80), 0);
        assert_eq!(envelope.level_at(u64::MAX), 0);
    }

    #[test]
    fn stereo_cancellation_does_not_hide_audible_energy()
    {
        let pcm: Vec<_> = (0..40).flat_map(|_| [0.25, -0.25]).collect();
        let envelope = SpeechEnvelope::from_samples(&pcm, 2, 1000).unwrap();
        assert_eq!(envelope.duration_ms, 40);
        assert_eq!(envelope.level_at(0), 1000);
    }

    #[test]
    fn rejects_bad_pcm_and_suppresses_background_noise()
    {
        assert!(SpeechEnvelope::from_samples(&[0.0], 0, 1000).is_err());
        assert!(SpeechEnvelope::from_samples(&[0.0], 2, 1000).is_err());
        assert!(SpeechEnvelope::from_samples(&[f32::NAN], 1, 1000).is_err());
        assert_eq!(SpeechEnvelope::from_samples(&[0.001; 40], 1, 1000).unwrap().level_at(0), 0);
    }
}

use ai_ex_domain::AppError;

#[derive(Debug, Clone)]
pub struct AudioFrame
{
    pub samples: Vec<f32>,
    pub sample_rate: u32,
    pub channels: u16,
}

impl AudioFrame
{
    pub fn new(samples: Vec<f32>, sample_rate: u32, channels: u16) -> Result<Self, AppError>
    {
        if samples.is_empty()
        {
            return Err(AppError::configuration("audio frame must not be empty"));
        }
        if sample_rate == 0 || channels == 0
        {
            return Err(AppError::configuration(
                "audio frame requires positive sample rate and channels",
            ));
        }
        if !samples.iter().all(|sample| sample.is_finite())
        {
            return Err(AppError::protocol("audio frame contains non-finite samples"));
        }
        Ok(Self {
            samples,
            sample_rate,
            channels,
        })
    }

    pub fn rms(&self) -> f32
    {
        let power: f64 = self
            .samples
            .iter()
            .map(|sample| f64::from(*sample) * f64::from(*sample))
            .sum();
        (power / self.samples.len() as f64).sqrt() as f32
    }
}

#[derive(Debug, Clone)]
pub struct Utterance
{
    pub samples: Vec<f32>,
    pub sample_rate: u32,
    pub channels: u16,
}

#[derive(Debug, Clone)]
pub enum VadEvent
{
    SpeechStarted,
    SpeechContinued,
    SpeechEnded(Utterance),
}

#[derive(Debug, Clone)]
pub struct VadConfig
{
    pub start_threshold: f32,
    pub continue_threshold: f32,
    pub start_frames: usize,
    pub end_silence_frames: usize,
    pub max_utterance_frames: usize,
}

impl Default for VadConfig
{
    fn default() -> Self
    {
        Self {
            start_threshold: 0.025,
            continue_threshold: 0.012,
            start_frames: 3,
            end_silence_frames: 8,
            max_utterance_frames: 3_000,
        }
    }
}

impl VadConfig
{
    pub fn validate(&self) -> Result<(), AppError>
    {
        if !(0.0..=1.0).contains(&self.start_threshold)
            || !(0.0..=1.0).contains(&self.continue_threshold)
        {
            return Err(AppError::configuration("VAD thresholds must be between 0 and 1"));
        }
        if self.continue_threshold > self.start_threshold
        {
            return Err(AppError::configuration(
                "VAD continue threshold must not exceed start threshold",
            ));
        }
        if self.start_frames == 0
            || self.end_silence_frames == 0
            || self.max_utterance_frames == 0
        {
            return Err(AppError::configuration("VAD frame counts must be positive"));
        }
        Ok(())
    }
}

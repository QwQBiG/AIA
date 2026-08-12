use ai_ex_domain::AppError;
use async_trait::async_trait;

use crate::{
    AudioFrame, DuplexController, DuplexDirective, EnergyVad, TranscriberPort, Utterance,
    VadConfig,
};

struct FixedTranscriber
{
    transcript: String,
    calls: usize,
}

#[async_trait]
impl TranscriberPort for FixedTranscriber
{
    async fn transcribe(&mut self, _utterance: Utterance) -> Result<String, AppError>
    {
        self.calls += 1;
        Ok(self.transcript.clone())
    }
}

fn frame(level: f32) -> AudioFrame
{
    AudioFrame::new(vec![level; 160], 16_000, 1).expect("valid frame")
}

fn controller(transcript: &str) -> DuplexController<FixedTranscriber>
{
    let vad = EnergyVad::new(VadConfig {
        start_threshold: 0.2,
        continue_threshold: 0.1,
        start_frames: 2,
        end_silence_frames: 2,
        max_utterance_frames: 100,
    })
    .expect("valid VAD");
    DuplexController::new(
        vad,
        FixedTranscriber {
            transcript: transcript.to_owned(),
            calls: 0,
        },
    )
}

#[tokio::test]
async fn speech_start_requests_barge_in_then_submits_transcript()
{
    let mut controller = controller("  hello there  ");

    assert_eq!(controller.process_frame(frame(0.3)).await.unwrap(), None);
    assert_eq!(
        controller.process_frame(frame(0.3)).await.unwrap(),
        Some(DuplexDirective::InterruptCurrentTurn)
    );
    assert_eq!(controller.process_frame(frame(0.0)).await.unwrap(), None);
    assert_eq!(
        controller.process_frame(frame(0.0)).await.unwrap(),
        Some(DuplexDirective::SubmitTranscript("hello there".to_owned()))
    );
}

#[tokio::test]
async fn empty_transcript_is_not_submitted()
{
    let mut controller = controller("   ");
    controller.process_frame(frame(0.3)).await.unwrap();
    controller.process_frame(frame(0.3)).await.unwrap();
    controller.process_frame(frame(0.0)).await.unwrap();

    assert_eq!(controller.process_frame(frame(0.0)).await.unwrap(), None);
}

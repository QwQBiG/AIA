#![forbid(unsafe_code)]

#[cfg(any(feature = "native-playback", test))]
mod envelope;

#[cfg(feature = "native-playback")]
mod native;

use std::collections::BTreeSet;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use ai_ex_core::SpeechPort;
use ai_ex_domain::{AppError, ComponentHealth, Emotion, SpeechPlaybackSnapshot, TurnId};
use ai_ex_stage::{StageAction, StageCapability, StageExecutor};
use ai_ex_text::clean_for_speech;
use async_trait::async_trait;
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
pub struct AudioPlayer {
    generation: Arc<AtomicU64>,
}

impl AudioPlayer {
    #[cfg(feature = "native-playback")]
    pub async fn play_wav(&self, job: &SpeechJob, bytes: Vec<u8>) -> Result<(), AppError> {
        self.play_wav_observed(job, bytes, |_| {}).await
    }

    #[cfg(not(feature = "native-playback"))]
    pub async fn play_wav_observed<F>(
        &self,
        job: &SpeechJob,
        bytes: Vec<u8>,
        _observer: F,
    ) -> Result<(), AppError>
    where
        F: Fn(ai_ex_domain::SpeechPlaybackSnapshot) + Send + 'static,
    {
        self.play_wav(job, bytes).await
    }

    #[cfg(not(feature = "native-playback"))]
    pub async fn play_wav(&self, job: &SpeechJob, _bytes: Vec<u8>) -> Result<(), AppError> {
        if self.cancelled(job) {
            return Ok(());
        }
        Err(AppError::unavailable(
            "binary was built without the native-playback feature",
        ))
    }

    #[cfg(feature = "native-playback")]
    pub async fn health(&self) -> ComponentHealth {
        match tokio::task::spawn_blocking(rodio::OutputStreamBuilder::open_default_stream).await {
            Ok(Ok(_stream)) => ComponentHealth::ready("audio-output"),
            Ok(Err(error)) => ComponentHealth::unavailable("audio-output", error.to_string()),
            Err(error) => ComponentHealth::unavailable("audio-output", error.to_string()),
        }
    }

    fn cancelled(&self, job: &SpeechJob) -> bool {
        job.generation != self.generation.load(Ordering::Acquire)
    }

    pub async fn wait_for_cancellation(&self, job: &SpeechJob) {
        while !self.cancelled(job) {
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
    }

    #[cfg(not(feature = "native-playback"))]
    pub async fn health(&self) -> ComponentHealth {
        ComponentHealth::unavailable(
            "audio-output",
            "binary was built without the native-playback feature",
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpeechJob {
    pub turn_id: TurnId,
    pub text: String,
    pub sentence_id: uuid::Uuid,
    pub emotion: Emotion,
    generation: u64,
}

impl SpeechJob {
    pub fn playback_snapshot(
        &self,
        position_ms: u64,
        duration_ms: u64,
        mouth_level: u16,
    ) -> SpeechPlaybackSnapshot {
        SpeechPlaybackSnapshot {
            turn_id: Some(self.turn_id),
            active: true,
            sentence_id: Some(self.sentence_id),
            text: self.text.clone(),
            emotion: Some(self.emotion),
            position_ms: position_ms.min(duration_ms),
            duration_ms,
            mouth_level: mouth_level.min(1000),
        }
    }
}

pub struct SpeechQueue {
    sender: mpsc::Sender<SpeechJob>,
    generation: Arc<AtomicU64>,
}

pub struct SpeechReceiver {
    receiver: mpsc::Receiver<SpeechJob>,
    generation: Arc<AtomicU64>,
}

impl SpeechQueue {
    pub fn new(capacity: usize) -> Result<(Self, SpeechReceiver), AppError> {
        if capacity == 0 {
            return Err(AppError::configuration(
                "audio queue capacity must be positive",
            ));
        }
        let (sender, receiver) = mpsc::channel(capacity);
        let generation = Arc::new(AtomicU64::new(0));
        Ok((
            Self {
                sender,
                generation: Arc::clone(&generation),
            },
            SpeechReceiver {
                receiver,
                generation,
            },
        ))
    }

    pub fn health(&self) -> ComponentHealth {
        if self.sender.is_closed() {
            ComponentHealth::unavailable("audio-queue", "consumer stopped")
        } else {
            ComponentHealth::ready("audio-queue")
        }
    }
}

impl SpeechReceiver {
    pub fn player(&self) -> AudioPlayer {
        AudioPlayer {
            generation: Arc::clone(&self.generation),
        }
    }

    pub async fn receive(&mut self) -> Option<SpeechJob> {
        while let Some(job) = self.receiver.recv().await {
            if job.generation == self.generation.load(Ordering::Acquire) {
                return Some(job);
            }
        }
        None
    }
}

#[async_trait]
impl SpeechPort for SpeechQueue {
    async fn enqueue(&mut self, turn_id: TurnId, sentence: String) -> Result<(), AppError> {
        self.enqueue_expressive(turn_id, sentence, Emotion::Neutral)
            .await
    }

    async fn enqueue_expressive(
        &mut self,
        turn_id: TurnId,
        sentence: String,
        emotion: Emotion,
    ) -> Result<(), AppError> {
        let sentence = clean_for_speech(&sentence);
        if sentence.is_empty() {
            return Err(AppError::configuration("speech sentence must not be empty"));
        }
        let job = SpeechJob {
            turn_id,
            text: sentence,
            sentence_id: uuid::Uuid::new_v4(),
            emotion,
            generation: self.generation.load(Ordering::Acquire),
        };
        self.sender
            .send(job)
            .await
            .map_err(|_| AppError::unavailable("audio queue consumer stopped"))
    }

    async fn interrupt(&mut self) -> Result<(), AppError> {
        self.generation.fetch_add(1, Ordering::AcqRel);
        Ok(())
    }
}

#[async_trait]
impl StageExecutor for SpeechQueue {
    fn capabilities(&self) -> BTreeSet<StageCapability> {
        BTreeSet::from([StageCapability::Interrupt, StageCapability::Speech])
    }

    async fn health(&self) -> ComponentHealth {
        SpeechQueue::health(self)
    }

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError> {
        action.validate()?;
        match action {
            StageAction::Speak {
                turn_id,
                text,
                emotion,
                ..
            } => {
                SpeechPort::enqueue_expressive(
                    self,
                    turn_id,
                    text,
                    emotion.unwrap_or(Emotion::Neutral),
                )
                .await
            }
            StageAction::Stop => SpeechPort::interrupt(self).await,
            StageAction::Expression { .. }
            | StageAction::Mouth { .. }
            | StageAction::Subtitle { .. }
            | StageAction::Scene { .. }
            | StageAction::Hotkey { .. } => Err(AppError::configuration(
                "audio stage does not support this action",
            )),
        }
    }

    async fn interrupt(&mut self) -> Result<(), AppError> {
        SpeechPort::interrupt(self).await
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn cancellation_wakes_pending_synthesis_without_cancelling_new_jobs() {
        let (mut queue, mut receiver) = SpeechQueue::new(2).unwrap();
        let player = receiver.player();
        queue
            .enqueue(TurnId::new(), "old".to_owned())
            .await
            .unwrap();
        let old = receiver.receive().await.unwrap();
        SpeechPort::interrupt(&mut queue).await.unwrap();
        queue
            .enqueue(TurnId::new(), "new".to_owned())
            .await
            .unwrap();
        let new = receiver.receive().await.unwrap();
        tokio::time::timeout(
            std::time::Duration::from_millis(100),
            player.wait_for_cancellation(&old),
        )
        .await
        .unwrap();
        assert!(!player.cancelled(&new));
    }

    #[tokio::test]
    async fn stage_executor_routes_speech_and_interrupts() {
        let (mut queue, mut receiver) = SpeechQueue::new(2).expect("queue created");
        let capabilities = StageExecutor::capabilities(&queue);
        assert!(capabilities.contains(&StageCapability::Speech));
        StageExecutor::execute(
            &mut queue,
            StageAction::Speak {
                turn_id: TurnId::new(),
                text: "hello".to_owned(),
                interruptible: true,
                emotion: None,
            },
        )
        .await
        .expect("speech action queues");
        assert_eq!(receiver.receive().await.expect("speech job").text, "hello");
        StageExecutor::execute(&mut queue, StageAction::Stop)
            .await
            .expect("stop interrupts");
        let error = StageExecutor::execute(
            &mut queue,
            StageAction::Scene {
                scene: "main".to_owned(),
            },
        )
        .await
        .expect_err("audio stage rejects scene");
        assert!(error.to_string().contains("audio stage"));
    }
    #[tokio::test]
    async fn interruption_invalidates_queued_speech() {
        let (mut queue, mut receiver) = SpeechQueue::new(4).expect("queue created");
        queue
            .enqueue(TurnId::new(), "old".to_owned())
            .await
            .expect("queued");
        SpeechPort::interrupt(&mut queue)
            .await
            .expect("interrupted");
        queue
            .enqueue(TurnId::new(), "new".to_owned())
            .await
            .expect("queued");
        let job = receiver.receive().await.expect("new job available");
        assert_eq!(job.text, "new");
    }

    #[tokio::test]
    async fn interruption_cancels_a_job_already_received() {
        let (mut queue, mut receiver) = SpeechQueue::new(4).expect("queue created");
        let player = receiver.player();
        queue
            .enqueue(TurnId::new(), "old".to_owned())
            .await
            .expect("queued");
        let job = receiver.receive().await.expect("job received");
        SpeechPort::interrupt(&mut queue)
            .await
            .expect("interrupted");

        player
            .play_wav(&job, vec![1, 2, 3])
            .await
            .expect("cancelled playback is skipped");
    }
}

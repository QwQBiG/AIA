#![forbid(unsafe_code)]

use std::collections::{BTreeSet, VecDeque};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use ai_ex_domain::{AppError, Emotion, StageActionSummary, StageSnapshot, TurnId, STAGE_TELEMETRY_SCHEMA_VERSION};
use ai_ex_stage::{StageAction, StageCapability, StageExecutor, StageRouter};
use async_trait::async_trait;
use tokio::sync::Mutex as AsyncMutex;

#[derive(Clone)]
pub struct StageJournal
{
    entries: Arc<Mutex<VecDeque<StageActionSummary>>>,
    next_sequence: Arc<AtomicU64>,
    capacity: usize,
    capabilities: Arc<Vec<String>>,
}

fn summarize_action(action: &StageAction) -> String
{
    match action
    {
        StageAction::Speak {
            turn_id,
            text,
            interruptible,
            ..
        } => format!("turn_id={turn_id:?} text_chars={} interruptible={interruptible}", text.chars().count()),
        StageAction::Subtitle {
            text,
            duration_ms,
        } => format!("text_chars={} duration_ms={duration_ms}", text.chars().count()),
        StageAction::Expression { emotion } => format!("emotion={emotion:?}"),
        StageAction::Mouth { value } => format!("value={value:.3}"),
        StageAction::Scene { scene } => format!("scene={scene}"),
        StageAction::Hotkey { id } => format!("id={id}"),
        StageAction::Stop => "stop".to_owned(),
    }
}

impl StageJournal
{
    pub fn new(capacity: usize) -> Self
    {
        Self::with_capabilities(capacity, BTreeSet::new())
    }

    pub fn with_capabilities(
        capacity: usize,
        capabilities: BTreeSet<StageCapability>,
    ) -> Self
    {
        let capabilities = capabilities
            .into_iter()
            .map(|capability| format!("{capability:?}").to_ascii_lowercase())
            .collect();
        Self {
            entries: Arc::new(Mutex::new(VecDeque::with_capacity(capacity.max(1)))),
            next_sequence: Arc::new(AtomicU64::new(0)),
            capacity: capacity.max(1),
            capabilities: Arc::new(capabilities),
        }
    }

    pub fn record(&self, action: &StageAction)
    {
        let sequence = self.next_sequence.fetch_add(1, Ordering::AcqRel) + 1;
        let entry = StageActionSummary {
            sequence,
            schema_version: STAGE_TELEMETRY_SCHEMA_VERSION,
            kind: action.kind().to_owned(),
            detail: summarize_action(action),
        };
        let mut entries = self
            .entries
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if entries.len() == self.capacity
        {
            entries.pop_front();
        }
        entries.push_back(entry);
    }

    pub fn snapshot(&self) -> StageSnapshot
    {
        let entries = self
            .entries
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        StageSnapshot {
            schema_version: STAGE_TELEMETRY_SCHEMA_VERSION,
            actions: entries.iter().cloned().collect(),
            capabilities: self.capabilities.as_ref().clone(),
        }
    }
}

#[derive(Clone)]
pub struct StageOutput
{
    router: Arc<AsyncMutex<StageRouter>>,
    journal: StageJournal,
}

impl StageOutput
{
    pub fn new(router: StageRouter) -> Self
    {
        let capabilities = router.capabilities();
        Self {
            router: Arc::new(AsyncMutex::new(router)),
            journal: StageJournal::with_capabilities(256, capabilities),
        }
    }

    pub fn speech(&self) -> StageSpeechPort
    {
        StageSpeechPort {
            router: Arc::clone(&self.router),
            journal: self.journal.clone(),
        }
    }

    pub fn avatar(&self) -> StageAvatarPort
    {
        StageAvatarPort {
            router: Arc::clone(&self.router),
            journal: self.journal.clone(),
        }
    }

    pub fn journal(&self) -> StageJournal
    {
        self.journal.clone()
    }

}

#[derive(Clone)]
pub struct StageSpeechPort
{
    router: Arc<AsyncMutex<StageRouter>>,
    journal: StageJournal,
}

#[async_trait]
impl crate::SpeechPort for StageSpeechPort
{
    async fn enqueue(&mut self, turn_id: TurnId, sentence: String) -> Result<(), AppError>
    {
        self.enqueue_expressive(turn_id, sentence, Emotion::Neutral).await
    }

    async fn enqueue_expressive(&mut self, turn_id: TurnId, sentence: String, emotion: Emotion) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        let subtitle_enabled = router.capabilities().contains(&StageCapability::Subtitle);
        let speech = StageAction::Speak {
            turn_id,
            text: sentence.clone(),
            interruptible: true,
            emotion: Some(emotion),
        };
        self.journal.record(&speech);
        router.execute(speech).await?;
        if subtitle_enabled
        {
            let subtitle = StageAction::Subtitle {
                text: sentence.clone(),
                duration_ms: subtitle_duration_ms(&sentence),
            };
            self.journal.record(&subtitle);
            router.execute(subtitle).await?;
        }
        Ok(())
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        let action = StageAction::Stop;
        self.journal.record(&action);
        router.execute(action).await
    }
}

fn subtitle_duration_ms(text: &str) -> u64
{
    let characters = text.chars().count() as u64;
    characters.saturating_mul(72).clamp(1_200, 12_000)
}
#[derive(Clone)]
pub struct StageAvatarPort
{
    router: Arc<AsyncMutex<StageRouter>>,
    journal: StageJournal,
}

#[async_trait]
impl crate::AvatarPort for StageAvatarPort
{
    async fn set_speaking(&mut self, speaking: bool) -> Result<(), AppError>
    {
        let value = if speaking { 0.65 } else { 0.0 };
        let mut router = self.router.lock().await;
        let action = StageAction::Mouth { value };
        self.journal.record(&action);
        router.execute(action).await
    }

    async fn set_neutral(&mut self) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        let expression = StageAction::Expression {
            emotion: Emotion::Neutral,
        };
        self.journal.record(&expression);
        router.execute(expression).await?;
        let mouth = StageAction::Mouth { value: 0.0 };
        self.journal.record(&mouth);
        router.execute(mouth).await
    }

    async fn set_emotion(&mut self, emotion: Emotion) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        let action = StageAction::Expression { emotion };
        self.journal.record(&action);
        router.execute(action).await
    }
}

#[cfg(test)]
mod tests
{
    use super::*;
    use crate::{AvatarPort, SpeechPort};
    use ai_ex_stage::DryRunStage;

    #[tokio::test]
    async fn stage_output_bridges_speech_and_avatar_ports()
    {
        let mut router = StageRouter::new();
        router.push(DryRunStage::new(8).expect("stage creates"));
        let output = StageOutput::new(router);
        let mut speech = output.speech();
        let mut avatar = output.avatar();
        speech
            .enqueue(TurnId::new(), "hello".to_owned())
            .await
            .expect("speech bridges");
        avatar
            .set_emotion(Emotion::Happy)
            .await
            .expect("emotion bridges");
        avatar
            .set_speaking(true)
            .await
            .expect("mouth bridges");
        let snapshot = output.journal().snapshot();
        assert_eq!(snapshot.schema_version, STAGE_TELEMETRY_SCHEMA_VERSION);
        assert!(snapshot.capabilities.contains(&"speech".to_owned()));
        assert!(snapshot.capabilities.contains(&"expression".to_owned()));
        assert!(snapshot.actions.iter().any(|action| action.kind == "speak"));
        assert!(snapshot.actions.iter().any(|action| action.kind == "expression"));
        assert!(snapshot.actions.iter().any(|action| action.kind == "mouth"));
        assert!(!snapshot.actions.iter().any(|action| action.detail.contains("hello")));
    }
}

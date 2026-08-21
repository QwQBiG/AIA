#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use std::time::Duration;

use ai_ex_domain::{AppError, TurnId};
use ai_ex_protocol::{EventEnvelope, SCHEMA_VERSION};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::mpsc;

pub type LiveEventEnvelope = EventEnvelope<LiveEvent>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventPriority
{
    Emergency,
    Manual,
    Safety,
    Gift,
    Chat,
    Proactive,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum LiveEvent
{
    ChatMessage {
        message_id: String,
        user_id: String,
        display_name: String,
        text: String,
    },
    Follow {
        user_id: String,
        display_name: String,
    },
    Subscription {
        user_id: String,
        display_name: String,
        tier: String,
    },
    Gift {
        event_id: String,
        user_id: String,
        display_name: String,
        gift_name: String,
        count: u32,
    },
    Donation {
        event_id: String,
        user_id: String,
        display_name: String,
        amount_minor: u64,
        currency: String,
        message: String,
    },
    Mention {
        message_id: String,
        user_id: String,
        display_name: String,
        text: String,
    },
    Moderation {
        action: String,
        target_user_id: Option<String>,
        reason: String,
    },
    Timer {
        name: String,
    },
    GameObservation {
        game: String,
        observation: Value,
    },
    SystemNotice {
        level: String,
        text: String,
    },
}

impl LiveEvent
{
    pub fn priority(&self) -> EventPriority
    {
        match self
        {
            Self::Moderation { .. } | Self::SystemNotice { .. } => EventPriority::Safety,
            Self::Donation { .. } | Self::Gift { .. } => EventPriority::Gift,
            Self::ChatMessage { .. } | Self::Mention { .. } => EventPriority::Chat,
            Self::Follow { .. } | Self::Subscription { .. } => EventPriority::Chat,
            Self::Timer { .. } | Self::GameObservation { .. } => EventPriority::Proactive,
        }
    }

    fn dedupe_key(&self) -> Option<String>
    {
        match self
        {
            Self::ChatMessage { message_id, .. } | Self::Mention { message_id, .. } =>
            {
                Some(format!("message:{message_id}"))
            }
            Self::Gift { event_id, .. } | Self::Donation { event_id, .. } =>
            {
                Some(format!("event:{event_id}"))
            }
            _ => None,
        }
    }

    fn user_key(&self) -> Option<&str>
    {
        match self
        {
            Self::ChatMessage { user_id, .. }
            | Self::Follow { user_id, .. }
            | Self::Subscription { user_id, .. }
            | Self::Gift { user_id, .. }
            | Self::Donation { user_id, .. }
            | Self::Mention { user_id, .. } => Some(user_id),
            Self::Moderation { target_user_id, .. } => target_user_id.as_deref(),
            Self::Timer { .. } | Self::GameObservation { .. } | Self::SystemNotice { .. } => None,
        }
    }

    fn has_global_cooldown(&self) -> bool
    {
        matches!(self, Self::ChatMessage { .. } | Self::Mention { .. })
    }
}

pub fn envelope(source: impl Into<String>, session_id: uuid::Uuid, event: LiveEvent) -> LiveEventEnvelope
{
    EventEnvelope::new(source, session_id, None::<TurnId>, event)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EventPolicy
{
    pub per_user_cooldown_ms: u64,
    pub global_cooldown_ms: u64,
    pub max_queue: usize,
}

impl Default for EventPolicy
{
    fn default() -> Self
    {
        Self {
            per_user_cooldown_ms: 1_500,
            global_cooldown_ms: 100,
            max_queue: 256,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PublishOutcome
{
    Accepted,
    Duplicate,
    UserCooldown,
    GlobalCooldown,
    QueueFull,
}

pub struct EventBus
{
    sender: mpsc::Sender<LiveEventEnvelope>,
    policy: EventPolicy,
    seen: HashMap<String, u64>,
    last_user: HashMap<String, u64>,
    last_global: Option<u64>,
}

pub type EventReceiver = mpsc::Receiver<LiveEventEnvelope>;

impl EventBus
{
    pub fn new(policy: EventPolicy) -> (Self, EventReceiver)
    {
        let (sender, receiver) = mpsc::channel(policy.max_queue);
        (
            Self {
                sender,
                policy,
                seen: HashMap::new(),
                last_user: HashMap::new(),
                last_global: None,
            },
            receiver,
        )
    }

    pub fn publish(&mut self, event: LiveEventEnvelope) -> PublishOutcome
    {
        let now = event.timestamp_ms;
        if let Some(key) = event.payload.dedupe_key()
        {
            if self
                .seen
                .get(&key)
                .is_some_and(|previous| now.saturating_sub(*previous) < self.policy.per_user_cooldown_ms)
            {
                return PublishOutcome::Duplicate;
            }
            self.seen.insert(key, now);
        }
        if let Some(user_id) = event.payload.user_key()
        {
            if self
                .last_user
                .get(user_id)
                .is_some_and(|previous| now.saturating_sub(*previous) < self.policy.per_user_cooldown_ms)
            {
                return PublishOutcome::UserCooldown;
            }
            self.last_user.insert(user_id.to_owned(), now);
        }
        if event.payload.has_global_cooldown()
            && self
                .last_global
                .is_some_and(|previous| now.saturating_sub(previous) < self.policy.global_cooldown_ms)
        {
            return PublishOutcome::GlobalCooldown;
        }
        if event.payload.has_global_cooldown()
        {
            self.last_global = Some(now);
        }
        match self.sender.try_send(event)
        {
            Ok(()) => PublishOutcome::Accepted,
            Err(mpsc::error::TrySendError::Full(_)) => PublishOutcome::QueueFull,
            Err(mpsc::error::TrySendError::Closed(_)) => PublishOutcome::QueueFull,
        }
    }

    pub fn sender(&self) -> mpsc::Sender<LiveEventEnvelope>
    {
        self.sender.clone()
    }
}

pub struct JsonlRecorder
{
    writer: BufWriter<File>,
}

impl JsonlRecorder
{
    pub fn create(path: impl AsRef<Path>) -> Result<Self, AppError>
    {
        let file = File::create(path.as_ref()).map_err(|error| {
            AppError::unavailable(format!("cannot create event recording: {error}"))
        })?;
        Ok(Self {
            writer: BufWriter::new(file),
        })
    }

    pub fn record(&mut self, event: &LiveEventEnvelope) -> Result<(), AppError>
    {
        serde_json::to_writer(&mut self.writer, event)
            .map_err(|error| AppError::protocol(format!("cannot encode event recording: {error}")))?;
        self.writer
            .write_all(b"\n")
            .map_err(|error| AppError::unavailable(format!("cannot write event recording: {error}")))?;
        Ok(())
    }

    pub fn flush(&mut self) -> Result<(), AppError>
    {
        self.writer
            .flush()
            .map_err(|error| AppError::unavailable(format!("cannot flush event recording: {error}")))
    }
}

pub fn load_jsonl(path: impl AsRef<Path>) -> Result<Vec<LiveEventEnvelope>, AppError>
{
    let file = File::open(path.as_ref()).map_err(|error| {
        AppError::unavailable(format!("cannot open event recording: {error}"))
    })?;
    let reader = BufReader::new(file);
    let mut events = Vec::new();
    for (line_number, line) in reader.lines().enumerate()
    {
        let line = line.map_err(|error| {
            AppError::unavailable(format!("cannot read event line {}: {error}", line_number + 1))
        })?;
        if line.trim().is_empty()
        {
            continue;
        }
        let event = serde_json::from_str(&line).map_err(|error| {
            AppError::protocol(format!("invalid event line {}: {error}", line_number + 1))
        })?;
        events.push(event);
    }
    Ok(events)
}

pub fn replay_delay(previous_ms: u64, current_ms: u64, speed: f64) -> Duration
{
    let speed = if speed.is_finite() && speed > 0.0 { speed } else { 1.0 };
    let elapsed = current_ms.saturating_sub(previous_ms) as f64 / speed;
    Duration::from_millis(elapsed.min(u64::MAX as f64) as u64)
}

pub async fn replay_jsonl(
    path: impl AsRef<Path>,
    speed: f64,
    sender: &mpsc::Sender<LiveEventEnvelope>,
) -> Result<usize, AppError>
{
    let events = load_jsonl(path)?;
    let mut previous = None;
    for event in &events
    {
        if let Some(previous_ms) = previous
        {
            tokio::time::sleep(replay_delay(previous_ms, event.timestamp_ms, speed)).await;
        }
        sender
            .send(event.clone())
            .await
            .map_err(|_| AppError::unavailable("event replay receiver closed"))?;
        previous = Some(event.timestamp_ms);
    }
    Ok(events.len())
}

pub fn is_v1(event: &LiveEventEnvelope) -> bool
{
    event.schema_version == SCHEMA_VERSION
}

#[cfg(test)]
mod tests
{
    use super::*;
    use uuid::Uuid;

    fn chat(timestamp_ms: u64, message_id: &str) -> LiveEventEnvelope
    {
        let mut event = envelope(
            "simulator",
            Uuid::new_v4(),
            LiveEvent::ChatMessage {
                message_id: message_id.to_owned(),
                user_id: "user-1".to_owned(),
                display_name: "测试观众".to_owned(),
                text: "hello".to_owned(),
            },
        );
        event.timestamp_ms = timestamp_ms;
        event
    }

    #[test]
    fn bus_deduplicates_and_applies_cooldowns()
    {
        let (mut bus, mut receiver) = EventBus::new(EventPolicy {
            per_user_cooldown_ms: 100,
            global_cooldown_ms: 0,
            max_queue: 4,
        });
        assert_eq!(bus.publish(chat(1_000, "m-1")), PublishOutcome::Accepted);
        assert_eq!(bus.publish(chat(1_001, "m-1")), PublishOutcome::Duplicate);
        assert_eq!(bus.publish(chat(1_050, "m-2")), PublishOutcome::UserCooldown);
        assert!(receiver.try_recv().is_ok());
    }

    #[test]
    fn jsonl_recording_round_trips()
    {
        let path = std::env::temp_dir().join(format!("aiex-events-{}.jsonl", Uuid::new_v4()));
        let event = chat(10, "m-1");
        let mut recorder = JsonlRecorder::create(&path).expect("recorder creates");
        recorder.record(&event).expect("event records");
        recorder.flush().expect("recording flushes");
        let loaded = load_jsonl(&path).expect("recording loads");
        std::fs::remove_file(&path).expect("recording removes");
        assert_eq!(loaded, vec![event]);
    }

    #[test]
    fn replay_speed_scales_delay_and_invalid_speed_is_safe()
    {
        assert_eq!(replay_delay(100, 1_100, 10.0), Duration::from_millis(100));
        assert_eq!(replay_delay(100, 1_100, 0.0), Duration::from_millis(1_000));
    }
}

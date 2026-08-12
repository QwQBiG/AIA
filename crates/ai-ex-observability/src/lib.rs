#![forbid(unsafe_code)]

use std::collections::VecDeque;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicU64, Ordering},
};

use ai_ex_core::EventSink;
use ai_ex_domain::{AppError, ConversationState, Emotion, SystemEvent, TurnId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use tokio::sync::{broadcast, watch};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeSnapshot
{
    pub state: ConversationState,
    pub active_turn: Option<TurnId>,
    pub current_emotion: Option<Emotion>,
    pub turns_started: u64,
    pub turns_completed: u64,
    pub turns_interrupted: u64,
    pub sentences_ready: u64,
    pub faults: u64,
    pub last_fault: Option<String>,
    pub last_sequence: u64,
}

impl Default for RuntimeSnapshot
{
    fn default() -> Self
    {
        Self {
            state: ConversationState::Idle,
            active_turn: None,
            current_emotion: None,
            turns_started: 0,
            turns_completed: 0,
            turns_interrupted: 0,
            sentences_ready: 0,
            faults: 0,
            last_fault: None,
            last_sequence: 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SequencedEvent
{
    pub sequence: u64,
    pub event: SystemEvent,
}

#[derive(Clone)]
pub struct EventHub
{
    events: broadcast::Sender<SequencedEvent>,
    snapshot: watch::Sender<RuntimeSnapshot>,
    sequence: Arc<AtomicU64>,
    history: Arc<Mutex<VecDeque<SequencedEvent>>>,
    capacity: usize,
}

impl EventHub
{
    pub fn new(capacity: usize) -> Result<Self, AppError>
    {
        if capacity == 0
        {
            return Err(AppError::configuration("event hub capacity must be positive"));
        }
        let (events, _receiver) = broadcast::channel(capacity);
        let (snapshot, _receiver) = watch::channel(RuntimeSnapshot::default());
        Ok(Self {
            events,
            snapshot,
            sequence: Arc::new(AtomicU64::new(0)),
            history: Arc::new(Mutex::new(VecDeque::with_capacity(capacity))),
            capacity,
        })
    }

    pub fn subscribe(&self) -> broadcast::Receiver<SequencedEvent>
    {
        self.events.subscribe()
    }

    pub fn watch(&self) -> watch::Receiver<RuntimeSnapshot>
    {
        self.snapshot.subscribe()
    }

    pub fn current(&self) -> RuntimeSnapshot
    {
        self.snapshot.borrow().clone()
    }

    pub fn events_since(&self, after: u64, limit: usize) -> Vec<SequencedEvent>
    {
        let history = self
            .history
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        history
            .iter()
            .filter(|item| item.sequence > after)
            .take(limit.min(self.capacity))
            .cloned()
            .collect()
    }

    fn update(&self, event: &SystemEvent, sequence: u64)
    {
        self.snapshot.send_modify(|snapshot|
        {
            snapshot.last_sequence = sequence;
            match event
            {
                SystemEvent::TurnStarted { turn_id, .. } =>
                {
                    snapshot.active_turn = Some(*turn_id);
                    snapshot.turns_started += 1;
                }
                SystemEvent::SentenceReady { .. } => snapshot.sentences_ready += 1,
                SystemEvent::EmotionChanged { emotion, .. } =>
                {
                    snapshot.current_emotion = Some(*emotion);
                }
                SystemEvent::TurnFinished { .. } =>
                {
                    snapshot.active_turn = None;
                    snapshot.current_emotion = None;
                    snapshot.turns_completed += 1;
                }
                SystemEvent::TurnInterrupted { .. } =>
                {
                    snapshot.active_turn = None;
                    snapshot.current_emotion = None;
                    snapshot.turns_interrupted += 1;
                }
                SystemEvent::StateChanged { to, .. } => snapshot.state = *to,
                SystemEvent::Fault { message } =>
                {
                    snapshot.faults += 1;
                    snapshot.last_fault = Some(message.clone());
                }
                SystemEvent::ModelChunk { .. } =>
                {
                }
            }
        });
    }
}

#[async_trait]
impl EventSink for EventHub
{
    async fn publish(&mut self, event: SystemEvent)
    {
        let sequence = self.sequence.fetch_add(1, Ordering::AcqRel) + 1;
        self.update(&event, sequence);
        let event = SequencedEvent { sequence, event };
        {
            let mut history = self
                .history
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            if history.len() == self.capacity
            {
                history.pop_front();
            }
            history.push_back(event.clone());
        }
        let _ignored = self.events.send(event);
    }
}

pub struct TeeEventSink<A, B>
{
    first: A,
    second: B,
}

impl<A, B> TeeEventSink<A, B>
{
    pub fn new(first: A, second: B) -> Self
    {
        Self { first, second }
    }
}

#[async_trait]
impl<A, B> EventSink for TeeEventSink<A, B>
where
    A: EventSink,
    B: EventSink,
{
    async fn publish(&mut self, event: SystemEvent)
    {
        self.first.publish(event.clone()).await;
        self.second.publish(event).await;
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[tokio::test]
    async fn broadcasts_events_and_updates_snapshot()
    {
        let mut hub = EventHub::new(8).expect("event hub");
        let mut events = hub.subscribe();
        let turn_id = TurnId::new();

        hub.publish(SystemEvent::TurnStarted {
            turn_id,
            user_text: "hello".to_owned(),
        })
        .await;
        hub.publish(SystemEvent::StateChanged {
            from: ConversationState::Idle,
            to: ConversationState::Thinking,
        })
        .await;
        hub.publish(SystemEvent::SentenceReady {
            turn_id,
            text: "hi".to_owned(),
        })
        .await;
        hub.publish(SystemEvent::TurnFinished {
            turn_id,
            full_text: "hi".to_owned(),
        })
        .await;

        let snapshot = hub.current();
        assert_eq!(snapshot.state, ConversationState::Thinking);
        assert_eq!(snapshot.active_turn, None);
        assert_eq!(snapshot.turns_started, 1);
        assert_eq!(snapshot.turns_completed, 1);
        assert_eq!(snapshot.sentences_ready, 1);
        assert_eq!(snapshot.last_sequence, 4);
        for sequence in 1..=4
        {
            assert_eq!(
                events.try_recv().expect("broadcast event").sequence,
                sequence,
            );
        }
        assert!(events.try_recv().is_err());
    }

    #[tokio::test]
    async fn replay_is_ordered_and_bounded()
    {
        let mut hub = EventHub::new(2).expect("event hub");
        for index in 0..3
        {
            hub.publish(SystemEvent::Fault {
                message: format!("fault {index}"),
            })
            .await;
        }

        let replay = hub.events_since(0, 10);
        assert_eq!(
            replay.iter().map(|item| item.sequence).collect::<Vec<_>>(),
            vec![2, 3],
        );
        assert_eq!(hub.events_since(2, 1)[0].sequence, 3);
    }

    #[test]
    fn rejects_zero_capacity()
    {
        assert!(EventHub::new(0).is_err());
    }
}

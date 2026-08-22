#![forbid(unsafe_code)]

use ai_ex_domain::{AppError, ConversationState, SystemEvent, TurnId};
use ai_ex_observability::{RuntimeSnapshot, SequencedEvent};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionState
{
    Disconnected,
    Connecting,
    Connected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TurnStatus
{
    Streaming,
    Completed,
    Interrupted,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UiTurn
{
    pub turn_id: TurnId,
    pub user_text: String,
    pub assistant_text: String,
    pub status: TurnStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApplyOutcome
{
    Applied,
    Duplicate,
    GapDetected,
}

pub struct UiState
{
    pub connection: ConnectionState,
    pub runtime: RuntimeSnapshot,
    pub turns: Vec<UiTurn>,
    pub needs_resync: bool,
    max_turns: usize,
}

impl UiState
{
    pub fn new(max_turns: usize) -> Result<Self, AppError>
    {
        if max_turns == 0
        {
            return Err(AppError::configuration("UI turn capacity must be positive"));
        }
        Ok(Self {
            connection: ConnectionState::Disconnected,
            runtime: RuntimeSnapshot::default(),
            turns: Vec::new(),
            needs_resync: false,
            max_turns,
        })
    }

    pub fn apply_snapshot(&mut self, snapshot: RuntimeSnapshot)
    {
        self.runtime = snapshot;
        self.needs_resync = false;
    }

    pub fn apply_event(&mut self, item: SequencedEvent) -> ApplyOutcome
    {
        if item.sequence <= self.runtime.last_sequence
        {
            return ApplyOutcome::Duplicate;
        }
        let gap = self.runtime.last_sequence != 0
            && item.sequence != self.runtime.last_sequence.saturating_add(1);
        if gap
        {
            self.needs_resync = true;
            return ApplyOutcome::GapDetected;
        }
        self.runtime.last_sequence = item.sequence;
        self.reduce(item.event);
        ApplyOutcome::Applied
    }

    fn reduce(&mut self, event: SystemEvent)
    {
        match event
        {
            SystemEvent::TurnStarted { turn_id, user_text } =>
            {
                self.runtime.active_turn = Some(turn_id);
                self.runtime.turns_started += 1;
                self.turns.push(UiTurn {
                    turn_id,
                    user_text,
                    assistant_text: String::new(),
                    status: TurnStatus::Streaming,
                });
                if self.turns.len() > self.max_turns
                {
                    self.turns.remove(0);
                }
            }
            SystemEvent::ModelChunk { turn_id, text } =>
            {
                if let Some(turn) = self.find_turn(turn_id)
                {
                    turn.assistant_text.push_str(&text);
                }
                else
                {
                    self.needs_resync = true;
                }
            }
            SystemEvent::SentenceReady { .. } => self.runtime.sentences_ready += 1,
            SystemEvent::EmotionChanged { emotion, .. } =>
            {
                self.runtime.current_emotion = Some(emotion);
            }
            SystemEvent::TurnFinished { turn_id, full_text } =>
            {
                self.runtime.active_turn = None;
                self.runtime.current_emotion = None;
                self.runtime.turns_completed += 1;
                self.finish_turn(turn_id, full_text, TurnStatus::Completed);
            }
            SystemEvent::TurnInterrupted { turn_id, .. } =>
            {
                self.runtime.active_turn = None;
                self.runtime.current_emotion = None;
                self.runtime.turns_interrupted += 1;
                self.set_status(turn_id, TurnStatus::Interrupted);
            }
            SystemEvent::StateChanged { to, .. } => self.runtime.state = to,
            SystemEvent::Fault { message } =>
            {
                self.runtime.state = ConversationState::Failed;
                self.runtime.faults += 1;
                self.runtime.last_fault = Some(message);
                if let Some(turn) = self.turns.last_mut()
                {
                    turn.status = TurnStatus::Failed;
                }
            }
            SystemEvent::LiveEventReceived { .. } | SystemEvent::LiveResponseSuggested { .. }
                | SystemEvent::PersonaChanged { .. }
                | SystemEvent::ComponentHealthChanged { .. } =>
            {
            }
        }
    }

    fn find_turn(&mut self, turn_id: TurnId) -> Option<&mut UiTurn>
    {
        self.turns.iter_mut().rev().find(|turn| turn.turn_id == turn_id)
    }

    fn finish_turn(&mut self, turn_id: TurnId, text: String, status: TurnStatus)
    {
        if let Some(turn) = self.find_turn(turn_id)
        {
            turn.assistant_text = text;
            turn.status = status;
        }
        else
        {
            self.needs_resync = true;
        }
    }

    fn set_status(&mut self, turn_id: TurnId, status: TurnStatus)
    {
        if let Some(turn) = self.find_turn(turn_id)
        {
            turn.status = status;
        }
        else
        {
            self.needs_resync = true;
        }
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    fn item(sequence: u64, event: SystemEvent) -> SequencedEvent
    {
        SequencedEvent { sequence, event }
    }

    #[test]
    fn assembles_a_streaming_turn_and_ignores_duplicates()
    {
        let mut state = UiState::new(10).expect("UI state");
        let turn_id = TurnId::new();
        state.apply_event(item(
            1,
            SystemEvent::TurnStarted {
                turn_id,
                user_text: "hello".to_owned(),
            },
        ));
        let chunk = item(
            2,
            SystemEvent::ModelChunk {
                turn_id,
                text: "hi".to_owned(),
            },
        );
        assert_eq!(state.apply_event(chunk.clone()), ApplyOutcome::Applied);
        assert_eq!(state.apply_event(chunk), ApplyOutcome::Duplicate);
        state.apply_event(item(
            3,
            SystemEvent::TurnFinished {
                turn_id,
                full_text: "hi there".to_owned(),
            },
        ));

        assert_eq!(state.turns[0].assistant_text, "hi there");
        assert_eq!(state.turns[0].status, TurnStatus::Completed);
        assert_eq!(state.runtime.turns_completed, 1);
    }

    #[test]
    fn detects_a_sequence_gap()
    {
        let mut state = UiState::new(10).expect("UI state");
        state.apply_event(item(
            1,
            SystemEvent::StateChanged {
                from: ConversationState::Idle,
                to: ConversationState::Thinking,
            },
        ));

        assert_eq!(
            state.apply_event(item(
                3,
                SystemEvent::StateChanged {
                    from: ConversationState::Thinking,
                    to: ConversationState::Speaking,
                },
            )),
            ApplyOutcome::GapDetected,
        );
        assert!(state.needs_resync);
        assert_eq!(state.runtime.last_sequence, 1);
        assert_eq!(state.runtime.state, ConversationState::Thinking);
    }

    #[test]
    fn bounds_conversation_history()
    {
        let mut state = UiState::new(2).expect("UI state");
        let mut ids = Vec::new();
        for sequence in 1..=3
        {
            let turn_id = TurnId::new();
            ids.push(turn_id);
            state.apply_event(item(
                sequence,
                SystemEvent::TurnStarted {
                    turn_id,
                    user_text: sequence.to_string(),
                },
            ));
        }

        assert_eq!(state.turns.len(), 2);
        assert_eq!(state.turns[0].turn_id, ids[1]);
    }
}

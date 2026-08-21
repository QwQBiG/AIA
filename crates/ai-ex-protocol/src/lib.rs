#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

use ai_ex_domain::{AppError, ComponentHealth, Message, TurnId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::mpsc;
use uuid::Uuid;

pub const SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModelRequest
{
    pub turn_id: TurnId,
    pub messages: Vec<Message>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl ModelRequest
{
    pub fn new(turn_id: TurnId, messages: Vec<Message>) -> Self
    {
        Self {
            turn_id,
            messages,
            metadata: BTreeMap::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilitySet
{
    pub text: bool,
    pub vision: bool,
    pub audio: bool,
    pub tool_call: bool,
    pub structured_output: bool,
    pub reasoning: bool,
    pub cancellation: bool,
}

impl CapabilitySet
{
    pub const fn text_only() -> Self
    {
        Self {
            text: true,
            vision: false,
            audio: false,
            tool_call: false,
            structured_output: false,
            reasoning: false,
            cancellation: false,
        }
    }
}

impl Default for CapabilitySet
{
    fn default() -> Self
    {
        Self::text_only()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ModelStreamEvent
{
    TextDelta { turn_id: TurnId, text: String },
    ReasoningDelta { turn_id: TurnId, text: String },
    ToolCall {
        turn_id: TurnId,
        call_id: String,
        name: String,
        arguments: Value,
    },
    StructuredOutput { turn_id: TurnId, value: Value },
    Usage {
        turn_id: TurnId,
        input_tokens: u32,
        output_tokens: u32,
    },
    Finished { turn_id: TurnId, finish_reason: Option<String> },
    Failed { turn_id: TurnId, error: AppError },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventEnvelope<T>
{
    pub schema_version: u16,
    pub event_id: Uuid,
    pub trace_id: Uuid,
    pub session_id: Uuid,
    pub turn_id: Option<TurnId>,
    pub timestamp_ms: u64,
    pub source: String,
    pub payload: T,
}

impl<T> EventEnvelope<T>
{
    pub fn new(source: impl Into<String>, session_id: Uuid, turn_id: Option<TurnId>, payload: T) -> Self
    {
        Self {
            schema_version: SCHEMA_VERSION,
            event_id: Uuid::new_v4(),
            trace_id: Uuid::new_v4(),
            session_id,
            turn_id,
            timestamp_ms: now_ms(),
            source: source.into(),
            payload,
        }
    }
}

fn now_ms() -> u64
{
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().min(u128::from(u64::MAX)) as u64)
        .unwrap_or_default()
}

pub type ModelStream = mpsc::Receiver<Result<ModelStreamEvent, AppError>>;

#[async_trait]
pub trait ModelBackend: Send
{
    fn capabilities(&self) -> CapabilitySet;

    async fn health(&self) -> ComponentHealth;

    async fn stream(&mut self, request: ModelRequest) -> Result<ModelStream, AppError>;

    async fn cancel(&mut self, turn_id: TurnId) -> Result<(), AppError>;
}

#[cfg(test)]
mod tests
{
    use super::*;
    use ai_ex_domain::{ErrorKind, Role};

    #[test]
    fn capability_defaults_to_text_only()
    {
        let capabilities = CapabilitySet::default();
        assert!(capabilities.text);
        assert!(!capabilities.tool_call);
        assert!(!capabilities.cancellation);
    }

    #[test]
    fn stream_events_round_trip_with_provider_specific_payloads()
    {
        let turn_id = TurnId::new();
        let event = ModelStreamEvent::ToolCall {
            turn_id,
            call_id: "call-1".to_owned(),
            name: "look".to_owned(),
            arguments: serde_json::json!({"screen": true}),
        };
        let encoded = serde_json::to_string(&event).expect("event serializes");
        let decoded: ModelStreamEvent = serde_json::from_str(&encoded).expect("event parses");
        assert_eq!(decoded, event);
    }

    #[test]
    fn envelope_contains_traceable_identity_and_schema_version()
    {
        let turn_id = TurnId::new();
        let envelope = EventEnvelope::new("deepseek", Uuid::new_v4(), Some(turn_id), "delta");
        assert_eq!(envelope.schema_version, SCHEMA_VERSION);
        assert_eq!(envelope.turn_id, Some(turn_id));
        assert!(!envelope.source.is_empty());
        assert!(envelope.timestamp_ms > 0);
    }

    #[test]
    fn model_request_preserves_message_order_and_metadata()
    {
        let turn_id = TurnId::new();
        let mut request = ModelRequest::new(
            turn_id,
            vec![Message::new(Role::User, "hello")],
        );
        request.metadata.insert("mode".to_owned(), "live".to_owned());
        let encoded = serde_json::to_string(&request).expect("request serializes");
        let decoded: ModelRequest = serde_json::from_str(&encoded).expect("request parses");
        assert_eq!(decoded, request);
    }

    #[test]
    fn failed_event_keeps_structured_error_kind()
    {
        let event = ModelStreamEvent::Failed {
            turn_id: TurnId::new(),
            error: AppError::unavailable("provider offline"),
        };
        let ModelStreamEvent::Failed { error, .. } = event else
        {
            panic!("expected failed event");
        };
        assert_eq!(error.kind, ErrorKind::Unavailable);
    }
}

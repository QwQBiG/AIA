use ai_ex_domain::{AppError, ComponentHealth, PersonaSnapshot, StageSnapshot};
use ai_ex_observability::{RuntimeSnapshot, SequencedEvent};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ControlRequest
{
    pub request_id: Uuid,
    pub token: String,
    pub command: ControlCommand,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ControlCommand
{
    Submit { text: String },
    Interrupt { reason: String },
    Status,
    Persona,
    SetPersona { profile: PersonaSnapshot },
    Health,
    Stage,
    Events { after: u64, limit: usize },
    EmergencyStop,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", content = "data", rename_all = "snake_case")]
pub enum ControlPayload
{
    Accepted,
    Snapshot(RuntimeSnapshot),
    Persona(PersonaSnapshot),
    Health(Vec<ComponentHealth>),
    Stage(StageSnapshot),
    Events(Vec<SequencedEvent>),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum ControlResponse
{
    Success {
        request_id: Uuid,
        payload: ControlPayload,
    },
    Failure {
        request_id: Option<Uuid>,
        error: AppError,
    },
}

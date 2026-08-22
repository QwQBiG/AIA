#![forbid(unsafe_code)]

mod actor;
mod engine;
mod ports;
mod protocol_adapter;
mod policy;
mod runtime;
mod stage_ports;
#[cfg(test)]
mod runtime_tests;

pub use engine::ConversationEngine;
pub use protocol_adapter::LegacyModelBackend;
pub use ports::{
    AvatarPort, EventSink, LanguageModelPort, MemoryPort, ModelRequest, SpeechPort,
};
pub use policy::ConversationPolicy;
pub use runtime::{Runtime, RuntimeControl, TurnOutcome};
pub use stage_ports::{StageAvatarPort, StageJournal, StageOutput, StageSpeechPort};
pub use actor::{RuntimeHandle, spawn_runtime};

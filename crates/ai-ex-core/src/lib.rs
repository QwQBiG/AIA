#![forbid(unsafe_code)]

mod actor;
mod engine;
mod ports;
mod policy;
mod runtime;
#[cfg(test)]
mod runtime_tests;

pub use engine::ConversationEngine;
pub use ports::{
    AvatarPort, EventSink, LanguageModelPort, MemoryPort, ModelRequest, SpeechPort,
};
pub use policy::ConversationPolicy;
pub use runtime::{Runtime, RuntimeControl, TurnOutcome};
pub use actor::{RuntimeHandle, spawn_runtime};

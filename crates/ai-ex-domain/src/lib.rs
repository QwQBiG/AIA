#![forbid(unsafe_code)]

mod conversation;
mod error;
mod event;
mod memory;
mod persona;

pub use conversation::{ConversationState, Emotion, Message, Role, TurnId};
pub use error::{AppError, ErrorKind};
pub use event::{ComponentHealth, LiveResponseMode, SystemEvent};
pub use memory::{MemoryKind, MemoryProjection};
pub use persona::PersonaSnapshot;

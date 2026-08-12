#![forbid(unsafe_code)]

mod conversation;
mod error;
mod event;

pub use conversation::{ConversationState, Emotion, Message, Role, TurnId};
pub use error::{AppError, ErrorKind};
pub use event::{ComponentHealth, SystemEvent};

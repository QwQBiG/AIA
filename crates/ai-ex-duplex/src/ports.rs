use ai_ex_domain::AppError;
use async_trait::async_trait;

use crate::{AudioFrame, Utterance};

#[async_trait]
pub trait AudioSourcePort: Send
{
    async fn next_frame(&mut self) -> Result<Option<AudioFrame>, AppError>;
}

#[async_trait]
pub trait TranscriberPort: Send
{
    async fn transcribe(&mut self, utterance: Utterance) -> Result<String, AppError>;
}

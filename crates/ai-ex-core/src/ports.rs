use ai_ex_domain::{AppError, Emotion, Message, SystemEvent, TurnId};
use async_trait::async_trait;
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
pub struct ModelRequest
{
    pub turn_id: TurnId,
    pub messages: Vec<Message>,
}

#[async_trait]
pub trait LanguageModelPort: Send
{
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError>;

    async fn cancel(&mut self, turn_id: TurnId) -> Result<(), AppError>;
}

#[async_trait]
pub trait SpeechPort: Send
{
    async fn enqueue(&mut self, turn_id: TurnId, sentence: String) -> Result<(), AppError>;
    async fn interrupt(&mut self) -> Result<(), AppError>;
}

#[async_trait]
pub trait AvatarPort: Send
{
    async fn set_speaking(&mut self, speaking: bool) -> Result<(), AppError>;
    async fn set_neutral(&mut self) -> Result<(), AppError>;

    async fn set_emotion(&mut self, _emotion: Emotion) -> Result<(), AppError>
    {
        Ok(())
    }
}

#[async_trait]
pub trait EventSink: Send
{
    async fn publish(&mut self, event: SystemEvent);
}

#[async_trait]
pub trait MemoryPort: Send + Sync
{
    async fn recall(&self, query: &str, limit: usize) -> Result<Vec<Message>, AppError>;

    async fn recall_for_context(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<Message>, AppError>
    {
        self.recall(query, limit).await
    }

    async fn remember(
        &mut self,
        turn_id: TurnId,
        user_text: String,
        assistant_text: String,
    ) -> Result<(), AppError>;
}

#![forbid(unsafe_code)]

use std::sync::Arc;

use ai_ex_domain::{AppError, Emotion, TurnId};
use ai_ex_stage::{StageAction, StageExecutor, StageRouter};
use async_trait::async_trait;
use tokio::sync::Mutex;

#[derive(Clone)]
pub struct StageOutput
{
    router: Arc<Mutex<StageRouter>>,
}

impl StageOutput
{
    pub fn new(router: StageRouter) -> Self
    {
        Self {
            router: Arc::new(Mutex::new(router)),
        }
    }

    pub fn speech(&self) -> StageSpeechPort
    {
        StageSpeechPort {
            router: Arc::clone(&self.router),
        }
    }

    pub fn avatar(&self) -> StageAvatarPort
    {
        StageAvatarPort {
            router: Arc::clone(&self.router),
        }
    }
}

#[derive(Clone)]
pub struct StageSpeechPort
{
    router: Arc<Mutex<StageRouter>>,
}

#[async_trait]
impl crate::SpeechPort for StageSpeechPort
{
    async fn enqueue(&mut self, turn_id: TurnId, sentence: String) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        router
            .execute(StageAction::Speak {
                turn_id,
                text: sentence,
                interruptible: true,
            })
            .await
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        router.execute(StageAction::Stop).await
    }
}

#[derive(Clone)]
pub struct StageAvatarPort
{
    router: Arc<Mutex<StageRouter>>,
}

#[async_trait]
impl crate::AvatarPort for StageAvatarPort
{
    async fn set_speaking(&mut self, speaking: bool) -> Result<(), AppError>
    {
        let value = if speaking { 0.65 } else { 0.0 };
        let mut router = self.router.lock().await;
        router.execute(StageAction::Mouth { value }).await
    }

    async fn set_neutral(&mut self) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        router
            .execute(StageAction::Expression {
                emotion: Emotion::Neutral,
            })
            .await?;
        router.execute(StageAction::Mouth { value: 0.0 }).await
    }

    async fn set_emotion(&mut self, emotion: Emotion) -> Result<(), AppError>
    {
        let mut router = self.router.lock().await;
        router.execute(StageAction::Expression { emotion }).await
    }
}

#[cfg(test)]
mod tests
{
    use super::*;
    use crate::{AvatarPort, SpeechPort};
    use ai_ex_stage::DryRunStage;

    #[tokio::test]
    async fn stage_output_bridges_speech_and_avatar_ports()
    {
        let mut router = StageRouter::new();
        router.push(DryRunStage::new(8).expect("stage creates"));
        let output = StageOutput::new(router);
        let mut speech = output.speech();
        let mut avatar = output.avatar();
        speech
            .enqueue(TurnId::new(), "hello".to_owned())
            .await
            .expect("speech bridges");
        avatar
            .set_emotion(Emotion::Happy)
            .await
            .expect("emotion bridges");
        avatar
            .set_speaking(true)
            .await
            .expect("mouth bridges");
    }
}
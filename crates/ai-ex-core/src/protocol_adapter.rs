use ai_ex_domain::{AppError, ComponentHealth, TurnId};
use ai_ex_protocol::{CapabilitySet, ModelBackend, ModelRequest as VersionedModelRequest};
use async_trait::async_trait;
use tokio::sync::mpsc;

use crate::{LanguageModelPort, ModelRequest};

/// Adapts the pre-Phase-2 text stream into the versioned provider protocol.
///
/// This keeps existing providers usable while new providers can implement
/// `ai_ex_protocol::ModelBackend` directly without changing the runtime.
pub struct LegacyModelBackend<M>
{
    inner: M,
}

impl<M> LegacyModelBackend<M>
{
    pub fn new(inner: M) -> Self
    {
        Self { inner }
    }

    pub fn into_inner(self) -> M
    {
        self.inner
    }
}

#[async_trait]
impl<M> ModelBackend for LegacyModelBackend<M>
where
    M: LanguageModelPort + Send + Sync,
{
    fn capabilities(&self) -> CapabilitySet
    {
        CapabilitySet {
            cancellation: true,
            ..CapabilitySet::text_only()
        }
    }

    async fn health(&self) -> ComponentHealth
    {
        ComponentHealth::ready("legacy-model-adapter")
    }

    async fn stream(
        &mut self,
        request: VersionedModelRequest,
    ) -> Result<ai_ex_protocol::ModelStream, AppError>
    {
        let turn_id = request.turn_id;
        let legacy_request = ModelRequest {
            turn_id,
            messages: request.messages,
        };
        let mut source = self.inner.stream(legacy_request).await?;
        let (sender, receiver) = mpsc::channel(32);
        tokio::spawn(async move
        {
            while let Some(item) = source.recv().await
            {
                match item
                {
                    Ok(text) =>
                    {
                        if sender
                            .send(Ok(ai_ex_protocol::ModelStreamEvent::TextDelta {
                                turn_id,
                                text,
                            }))
                            .await
                            .is_err()
                        {
                            return;
                        }
                    }
                    Err(error) =>
                    {
                        let _ignored = sender
                            .send(Ok(ai_ex_protocol::ModelStreamEvent::Failed {
                                turn_id,
                                error,
                            }))
                            .await;
                        return;
                    }
                }
            }
            let _ignored = sender
                .send(Ok(ai_ex_protocol::ModelStreamEvent::Finished {
                    turn_id,
                    finish_reason: Some("legacy_stream_closed".to_owned()),
                }))
                .await;
        });
        Ok(receiver)
    }

    async fn cancel(&mut self, turn_id: TurnId) -> Result<(), AppError>
    {
        self.inner.cancel(turn_id).await
    }
}
#[cfg(test)]
mod tests
{
    use super::*;
    use ai_ex_domain::{Message, Role};
    use ai_ex_protocol::{ModelBackend, ModelStreamEvent};

    struct MockModel;

    #[async_trait]
    impl LanguageModelPort for MockModel
    {
        async fn stream(
            &mut self,
            _request: ModelRequest,
        ) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError>
        {
            let (sender, receiver) = mpsc::channel(4);
            sender
                .send(Ok("hello".to_owned()))
                .await
                .expect("mock stream accepts text");
            Ok(receiver)
        }

        async fn cancel(&mut self, _turn_id: TurnId) -> Result<(), AppError>
        {
            Ok(())
        }
    }

    #[tokio::test]
    async fn converts_legacy_text_stream_to_versioned_events()
    {
        let turn_id = TurnId::new();
        let mut adapter = LegacyModelBackend::new(MockModel);
        let request = VersionedModelRequest::new(
            turn_id,
            vec![Message::new(Role::User, "hello")],
        );
        let mut stream = adapter.stream(request).await.expect("adapter starts");
        let first = stream
            .recv()
            .await
            .expect("text event exists")
            .expect("text event succeeds");
        assert_eq!(
            first,
            ModelStreamEvent::TextDelta {
                turn_id,
                text: "hello".to_owned(),
            }
        );
        let second = stream
            .recv()
            .await
            .expect("finish event exists")
            .expect("finish event succeeds");
        assert!(matches!(second, ModelStreamEvent::Finished { turn_id: id, .. } if id == turn_id));
    }
}
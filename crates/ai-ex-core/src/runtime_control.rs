use std::{future::Future, time::Duration};

use super::*;

const OUTPUT_TIMEOUT: Duration = Duration::from_millis(250);

pub(super) enum AvatarAction {
    Neutral,
    Stop,
    Subtitle(String),
    Speaking,
    Emotion(Emotion),
}

pub(super) async fn bounded(
    component: &str,
    operation: impl Future<Output = Result<(), AppError>>,
) -> Result<(), AppError> {
    tokio::time::timeout(OUTPUT_TIMEOUT, operation)
        .await
        .map_err(|_| AppError::unavailable(format!("{component} did not respond within 250 ms")))?
}

pub(super) async fn cancel_speech_port<S: SpeechPort, E: EventSink>(
    speech: &mut S,
    events: &mut E,
) -> Result<(), AppError> {
    events.publish(SystemEvent::SpeechCancelled).await;
    let result = bounded("speech cancellation", speech.interrupt()).await;
    if let Err(error) = &result {
        events
            .publish(SystemEvent::Fault {
                message: error.to_string(),
            })
            .await;
    }
    result
}

impl<M, S, A, N, E> Runtime<M, S, A, N, E>
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    pub(super) async fn avatar_output(&mut self, action: AvatarAction) {
        if !self.avatar_healthy && !matches!(action, AvatarAction::Neutral | AvatarAction::Stop) {
            return;
        }
        let can_recover = matches!(action, AvatarAction::Stop);
        let result = match action {
            AvatarAction::Stop => {
                bounded("avatar output", self.avatar.interrupt_presentation()).await
            }
            AvatarAction::Subtitle(text) => {
                bounded("avatar output", self.avatar.set_subtitle(text)).await
            }
            AvatarAction::Neutral => bounded("avatar output", self.avatar.set_neutral()).await,
            AvatarAction::Speaking => {
                bounded("avatar output", self.avatar.set_speaking(true)).await
            }
            AvatarAction::Emotion(emotion) => {
                bounded("avatar output", self.avatar.set_emotion(emotion)).await
            }
        };
        let ready = result.is_ok();
        if ready && !self.avatar_healthy && !can_recover {
            return;
        }
        if ready != self.avatar_healthy {
            self.avatar_healthy = ready;
            self.events
                .publish(SystemEvent::ComponentHealthChanged {
                    component: "avatar-output".to_owned(),
                    ready,
                    detail: result
                        .err()
                        .map(|error| error.to_string())
                        .unwrap_or_default(),
                })
                .await;
        }
    }
}

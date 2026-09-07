use ai_ex_domain::{MemoryRequest, MemoryResponse};
use tokio::sync::mpsc;

use super::*;

impl<M, S, A, N, E> Runtime<M, S, A, N, E>
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    pub async fn memory(&mut self, request: MemoryRequest) -> Result<MemoryResponse, AppError> {
        self.manage_memory(request, None).await.0
    }

    pub(crate) async fn manage_memory(
        &mut self,
        request: MemoryRequest,
        mut control: Option<&mut mpsc::Receiver<RuntimeControl>>,
    ) -> (Result<MemoryResponse, AppError>, bool) {
        if let Err(error) = request.validate() {
            return (Err(error), false);
        }
        if request.profile_id() != self.profile_id {
            return (
                Err(AppError::invalid_transition(
                    "memory profile does not match the current persona; refresh before retrying",
                )),
                false,
            );
        }
        if self.engine.active_turn().is_some() {
            return (
                Err(AppError::invalid_transition(
                    "memory management is unavailable during an active turn",
                )),
                false,
            );
        }
        let mutation = request.is_mutation();
        let mut shutdown = false;
        let result = {
            let operation = self.memory.manage(request);
            tokio::pin!(operation);
            if let Some(receiver) = control.as_mut() {
                let mut cancelled = false;
                loop {
                    tokio::select! {
                        result = &mut operation => break result,
                        Some(command) = receiver.recv() => {
                            shutdown |= matches!(command, RuntimeControl::Shutdown);
                            if !cancelled {
                                cancelled = true;
                                let _ignored = control::cancel_speech_port(
                                    &mut self.speech, &mut self.events,
                                ).await;
                                let _ignored = control::bounded(
                                    "avatar output", self.avatar.interrupt_presentation(),
                                ).await;
                            }
                        }
                    }
                }
            } else {
                operation.await
            }
        };
        // The durable operation must finish before history changes. A cancelled caller
        // still needs the same invalidation if its write was committed successfully.
        if mutation && result.is_ok() {
            self.engine.clear_identity_context();
            // Output cancellation cannot turn a committed edit into a failed edit.
            // Report output faults independently and still acknowledge the durable result.
            let _ignored = self.cancel_speech().await;
            self.avatar_output(AvatarAction::Stop).await;
        }
        (result, shutdown)
    }
}

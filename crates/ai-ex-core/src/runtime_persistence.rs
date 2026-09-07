use super::*;

impl<M, S, A, N, E> Runtime<M, S, A, N, E>
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    pub(super) async fn remember_turn(
        &mut self,
        turn_id: TurnId,
        input: String,
        assistant: String,
        control: Option<&mut tokio::sync::mpsc::Receiver<RuntimeControl>>,
    ) -> Result<bool, AppError> {
        let Some(receiver) = control else {
            self.memory.remember(turn_id, input, assistant).await?;
            return Ok(false);
        };
        let writing = self.memory.remember(turn_id, input, assistant);
        tokio::pin!(writing);
        let mut shutdown = false;
        let mut requested = false;
        let mut cancellation = None;
        let remembered = loop {
            tokio::select! {
                biased;
                result = &mut writing => break result,
                Some(command) = receiver.recv() => {
                    requested = true;
                    shutdown |= matches!(command, RuntimeControl::Shutdown);
                    if cancellation.is_none() {
                        cancellation = Some(control::cancel_speech_port(&mut self.speech, &mut self.events).await);
                    }
                }
            }
        };
        while let Ok(command) = receiver.try_recv() {
            requested = true;
            shutdown |= matches!(command, RuntimeControl::Shutdown);
        }
        if requested && cancellation.is_none() {
            cancellation =
                Some(control::cancel_speech_port(&mut self.speech, &mut self.events).await);
        }
        remembered?;
        cancellation.unwrap_or(Ok(()))?;
        Ok(shutdown)
    }
}

use std::collections::VecDeque;

use ai_ex_domain::AppError;
use tokio::sync::{mpsc, oneshot};

use crate::{
    AvatarPort, EventSink, LanguageModelPort, MemoryPort, Runtime, RuntimeControl, SpeechPort,
    TurnOutcome,
};

enum RuntimeCommand {
    Submit {
        input: String,
        response: oneshot::Sender<Result<TurnOutcome, AppError>>,
        admission: Option<oneshot::Sender<Result<(), AppError>>>,
    },
    Interrupt {
        reason: String,
        response: oneshot::Sender<Result<(), AppError>>,
    },
    SetSystemPrompt {
        prompt: String,
        response: oneshot::Sender<Result<(), AppError>>,
    },
    Shutdown {
        response: oneshot::Sender<Result<(), AppError>>,
    },
    SetPersona {
        profile_id: String,
        prompt: String,
        response: oneshot::Sender<Result<(), AppError>>,
    },
}

#[derive(Clone)]
pub struct RuntimeHandle {
    sender: mpsc::Sender<RuntimeCommand>,
}

/// An admitted turn whose generation can be awaited separately from enqueueing.
pub struct PendingTurn(oneshot::Receiver<Result<TurnOutcome, AppError>>);

impl PendingTurn {
    pub async fn wait(self) -> Result<TurnOutcome, AppError> {
        self.0
            .await
            .map_err(|_| AppError::unavailable("runtime response dropped"))?
    }
}

impl RuntimeHandle {
    pub async fn submit(&self, input: impl Into<String>) -> Result<TurnOutcome, AppError> {
        self.enqueue(input).await?.wait().await
    }

    /// Acknowledge only after the actor has reserved a turn or queue position.
    pub async fn enqueue(&self, input: impl Into<String>) -> Result<PendingTurn, AppError> {
        let (response, receiver) = oneshot::channel();
        let (admission, admitted) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::Submit {
                input: input.into(),
                response,
                admission: Some(admission),
            })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        admitted
            .await
            .map_err(|_| AppError::unavailable("runtime admission dropped"))??;
        Ok(PendingTurn(receiver))
    }

    pub async fn interrupt(&self, reason: impl Into<String>) -> Result<(), AppError> {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::Interrupt {
                reason: reason.into(),
                response,
            })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("interrupt response dropped"))?
    }

    pub async fn set_system_prompt(&self, prompt: impl Into<String>) -> Result<(), AppError> {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::SetSystemPrompt {
                prompt: prompt.into(),
                response,
            })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("persona update response dropped"))?
    }

    pub async fn shutdown(&self) -> Result<(), AppError> {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::Shutdown { response })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("shutdown response dropped"))?
    }

    pub async fn set_persona(&self, profile_id: String, prompt: String) -> Result<(), AppError> {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::SetPersona {
                profile_id,
                prompt,
                response,
            })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("persona update response dropped"))?
    }
}

pub fn spawn_runtime<M, S, A, N, E>(
    runtime: Runtime<M, S, A, N, E>,
    capacity: usize,
) -> Result<RuntimeHandle, AppError>
where
    M: LanguageModelPort + 'static,
    S: SpeechPort + 'static,
    A: AvatarPort + 'static,
    N: MemoryPort + 'static,
    E: EventSink + 'static,
{
    if capacity == 0 {
        return Err(AppError::configuration(
            "runtime actor capacity must be positive",
        ));
    }
    let (sender, receiver) = mpsc::channel(capacity);
    tokio::spawn(run_actor(runtime, receiver, capacity));
    Ok(RuntimeHandle { sender })
}

async fn run_actor<M, S, A, N, E>(
    mut runtime: Runtime<M, S, A, N, E>,
    mut receiver: mpsc::Receiver<RuntimeCommand>,
    pending_capacity: usize,
) where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    let mut stopping = false;
    let mut pending = VecDeque::new();
    loop {
        let command = match pending.pop_front() {
            Some(command) => command,
            None => match receiver.recv().await {
                Some(command) => command,
                None => break,
            },
        };
        match command {
            RuntimeCommand::Submit {
                input,
                response,
                admission,
            } => {
                if let Some(admission) = admission
                    && admission.send(Ok(())).is_err()
                {
                    continue;
                }
                let mut shutdown_response: Option<oneshot::Sender<Result<(), AppError>>> = None;
                let mut deferred_interrupt = None;
                {
                    let (control, mut control_receiver) = mpsc::channel(4);
                    let turn = runtime.run_turn_controlled(input, &mut control_receiver);
                    tokio::pin!(turn);
                    loop {
                        tokio::select! {
                            result = &mut turn =>
                            {
                                let _ignored = response.send(result);
                                break;
                            }
                            next = receiver.recv(), if !stopping =>
                            {
                                match next
                                {
                                    Some(RuntimeCommand::Interrupt { reason, response }) =>
                                    {
                                        deferred_interrupt = Some(reason.clone());
                                        let result = signal_control(&control, RuntimeControl::Interrupt { reason });
                                        let _ignored = response.send(result);
                                    }
                                    Some(RuntimeCommand::SetSystemPrompt { response, .. })
                                    | Some(RuntimeCommand::SetPersona { response, .. }) =>
                                    {
                                        let _ignored = response.send(Err(AppError::invalid_transition(
                                            "cannot change persona during an active turn",
                                        )));
                                    }
                                    Some(RuntimeCommand::Shutdown { response }) =>
                                    {
                                        let result = signal_control(&control, RuntimeControl::Shutdown);
                                        match result
                                        {
                                            Ok(()) =>
                                            {
                                                shutdown_response = Some(response);
                                                stopping = true;
                                            }
                                            Err(error) =>
                                            {
                                                let _ignored = response.send(Err(error));
                                            }
                                        }
                                    }
                                    Some(RuntimeCommand::Submit { input, response, admission }) =>
                                    {
                                        if pending.len() < pending_capacity {
                                            if admission.is_none_or(|admission| admission.send(Ok(())).is_ok()) {
                                                pending.push_back(RuntimeCommand::Submit { input, response, admission: None });
                                            }
                                        } else {
                                            let error = AppError::unavailable("conversation queue is full; wait for a pending turn");
                                            if let Some(admission) = admission {
                                                let _ignored = admission.send(Err(error.clone()));
                                            }
                                            let _ignored = response.send(Err(error));
                                        }
                                    }
                                    None =>
                                    {
                                        let _ignored = signal_control(&control, RuntimeControl::Shutdown);
                                        stopping = true;
                                    }
                                }
                            }
                        }
                    }
                }
                if stopping {
                    let result = runtime.stop().await;
                    if let Some(response) = shutdown_response.take() {
                        let _ignored = response.send(result);
                    }
                } else if let Some(reason) = deferred_interrupt {
                    // Covers an accepted command racing with the turn's final commit.
                    let _ignored = runtime.interrupt(reason).await;
                }
            }
            RuntimeCommand::Interrupt { reason, response } => {
                let _ignored = response.send(runtime.interrupt(reason).await);
            }
            RuntimeCommand::SetSystemPrompt { prompt, response } => {
                let _ignored = response.send(runtime.set_system_prompt(prompt));
            }
            RuntimeCommand::SetPersona {
                profile_id,
                prompt,
                response,
            } => {
                let _ignored = response.send(runtime.set_persona(profile_id, prompt).await);
            }
            RuntimeCommand::Shutdown { response } => {
                let result = runtime.stop().await;
                let _ignored = response.send(result);
                break;
            }
        }
        if stopping {
            break;
        }
    }
}

fn signal_control(
    sender: &mpsc::Sender<RuntimeControl>,
    command: RuntimeControl,
) -> Result<(), AppError> {
    match sender.try_send(command) {
        Ok(()) | Err(mpsc::error::TrySendError::Full(_)) => Ok(()),
        Err(mpsc::error::TrySendError::Closed(_)) => {
            Err(AppError::unavailable("turn control stopped"))
        }
    }
}

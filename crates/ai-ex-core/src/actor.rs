use std::collections::VecDeque;

use ai_ex_domain::AppError;
use tokio::sync::{mpsc, oneshot};

use crate::{
    AvatarPort, EventSink, LanguageModelPort, MemoryPort, Runtime, RuntimeControl, SpeechPort,
    TurnOutcome,
};

enum RuntimeCommand
{
    Submit {
        input: String,
        response: oneshot::Sender<Result<TurnOutcome, AppError>>,
    },
    Interrupt {
        reason: String,
        response: oneshot::Sender<Result<(), AppError>>,
    },
    Shutdown {
        response: oneshot::Sender<Result<(), AppError>>,
    },
}

#[derive(Clone)]
pub struct RuntimeHandle
{
    sender: mpsc::Sender<RuntimeCommand>,
}

impl RuntimeHandle
{
    pub async fn submit(&self, input: impl Into<String>) -> Result<TurnOutcome, AppError>
    {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::Submit {
                input: input.into(),
                response,
            })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("runtime response dropped"))?
    }

    pub async fn interrupt(&self, reason: impl Into<String>) -> Result<(), AppError>
    {
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

    pub async fn shutdown(&self) -> Result<(), AppError>
    {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(RuntimeCommand::Shutdown { response })
            .await
            .map_err(|_| AppError::unavailable("runtime actor stopped"))?;
        receiver
            .await
            .map_err(|_| AppError::unavailable("shutdown response dropped"))?
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
    if capacity == 0
    {
        return Err(AppError::configuration("runtime actor capacity must be positive"));
    }
    let (sender, receiver) = mpsc::channel(capacity);
    tokio::spawn(run_actor(runtime, receiver));
    Ok(RuntimeHandle { sender })
}

async fn run_actor<M, S, A, N, E>(
    mut runtime: Runtime<M, S, A, N, E>,
    mut receiver: mpsc::Receiver<RuntimeCommand>,
)
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    let mut stopping = false;
    let mut pending = VecDeque::new();
    loop
    {
        let command = match pending.pop_front()
        {
            Some(command) => command,
            None => match receiver.recv().await
            {
                Some(command) => command,
                None => break,
            },
        };
        match command
        {
            RuntimeCommand::Submit { input, response } =>
            {
                let mut shutdown_response: Option<oneshot::Sender<Result<(), AppError>>> = None;
                {
                    let (control, mut control_receiver) = mpsc::channel(4);
                    let turn = runtime.run_turn_controlled(input, &mut control_receiver);
                    tokio::pin!(turn);
                    loop
                    {
                        tokio::select!
                        {
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
                                        let result = control
                                            .send(RuntimeControl::Interrupt { reason })
                                            .await
                                            .map_err(|_| AppError::unavailable("turn control stopped"));
                                        let _ignored = response.send(result);
                                    }
                                    Some(RuntimeCommand::Shutdown { response }) =>
                                    {
                                        let result = control
                                            .send(RuntimeControl::Shutdown)
                                            .await
                                            .map_err(|_| AppError::unavailable("turn control stopped"));
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
                                    Some(command @ RuntimeCommand::Submit { .. }) =>
                                    {
                                        pending.push_back(command);
                                    }
                                    None =>
                                    {
                                        let _ignored = control.send(RuntimeControl::Shutdown).await;
                                        stopping = true;
                                    }
                                }
                            }
                        }
                    }
                }
                if stopping
                {
                    let result = runtime.stop().await;
                    if let Some(response) = shutdown_response.take()
                    {
                        let _ignored = response.send(result);
                    }
                }
            }
            RuntimeCommand::Interrupt { response, .. } =>
            {
                let _ignored = response.send(Err(AppError::invalid_transition(
                    "runtime has no active turn",
                )));
            }
            RuntimeCommand::Shutdown { response } =>
            {
                let result = runtime.stop().await;
                let _ignored = response.send(result);
                break;
            }
        }
        if stopping
        {
            break;
        }
    }
}

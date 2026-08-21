use std::sync::mpsc::{self, Receiver, Sender};
use std::time::Duration;

use ai_ex_control::{ControlClient, ControlCommand, ControlPayload};
use ai_ex_domain::{AppError, ComponentHealth};
use ai_ex_observability::{RuntimeSnapshot, SequencedEvent};
use tokio::sync::mpsc::{UnboundedReceiver, UnboundedSender};

const HEALTH_REFRESH_TICKS: u8 = 8;

pub struct WorkerSettings
{
    pub address: String,
    pub token: String,
    pub max_message_bytes: usize,
}

pub enum WorkerCommand
{
    Submit(String),
    Interrupt,
    EmergencyStop,
}

pub enum WorkerEvent
{
    Connection(bool),
    Snapshot(RuntimeSnapshot),
    Health(Vec<ComponentHealth>),
    Events(Vec<SequencedEvent>),
    Log(String),
    Failure(String),
}

pub struct WorkerHandle
{
    pub commands: UnboundedSender<WorkerCommand>,
    pub events: Receiver<WorkerEvent>,
}

pub fn spawn_worker(settings: WorkerSettings) -> Result<WorkerHandle, AppError>
{
    let client = ControlClient::new(
        &settings.address,
        settings.token,
        settings.max_message_bytes,
    )?;
    let (commands, command_receiver) = tokio::sync::mpsc::unbounded_channel();
    let (event_sender, events) = mpsc::channel();
    std::thread::Builder::new()
        .name("ai-ex-desktop-network".to_owned())
        .spawn(move ||
        {
            let runtime = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build();
            match runtime
            {
                Ok(runtime) => runtime.block_on(run_worker(client, command_receiver, event_sender)),
                Err(error) =>
                {
                    let _ignored = event_sender.send(WorkerEvent::Failure(format!(
                        "cannot start desktop network runtime: {error}",
                    )));
                }
            }
        })
        .map_err(|error| AppError::unavailable(format!("cannot start desktop worker: {error}")))?;
    Ok(WorkerHandle { commands, events })
}

async fn run_worker(
    client: ControlClient,
    mut commands: UnboundedReceiver<WorkerCommand>,
    events: Sender<WorkerEvent>,
)
{
    let mut interval = tokio::time::interval(Duration::from_millis(250));
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    let mut connected = false;
    let mut cursor = 0;
    let mut ticks = 0_u8;
    let mut failure_reported = false;
    loop
    {
        tokio::select!
        {
            command = commands.recv() =>
            {
                let Some(command) = command else
                {
                    return;
                };
                match send_command(&client, command).await
                {
                    Ok(()) =>
                    {
                        if !emit(&events, WorkerEvent::Log("control command sent".to_owned()))
                        {
                            return;
                        }
                    }
                    Err(error) =>
                    {
                        if !emit(&events, WorkerEvent::Failure(error.to_string()))
                        {
                            return;
                        }
                    }
                }
            }
            _ = interval.tick() =>
            {
                if !connected
                {
                    match fetch_snapshot(&client).await
                    {
                        Ok(snapshot) =>
                        {
                            let health = match fetch_health(&client).await
                            {
                                Ok(health) => health,
                                Err(error) =>
                                {
                                    if !failure_reported
                                    {
                                        failure_reported = true;
                                        if !emit(&events, WorkerEvent::Connection(false))
                                            || !emit(&events, WorkerEvent::Failure(error.to_string()))
                                        {
                                            return;
                                        }
                                    }
                                    continue;
                                }
                            };
                            cursor = snapshot.last_sequence;
                            connected = true;
                            failure_reported = false;
                            if !emit(&events, WorkerEvent::Connection(true))
                                || !emit(&events, WorkerEvent::Snapshot(snapshot))
                                || !emit(&events, WorkerEvent::Health(health))
                            {
                                return;
                            }
                        }
                        Err(error) =>
                        {
                            if !failure_reported
                            {
                                failure_reported = true;
                                if !emit(&events, WorkerEvent::Connection(false))
                                    || !emit(&events, WorkerEvent::Failure(error.to_string()))
                                {
                                    return;
                                }
                            }
                        }
                    }
                    continue;
                }
                match poll(&client, cursor).await
                {
                    Ok(items) =>
                    {
                        if let Some(last) = items.last()
                        {
                            cursor = last.sequence;
                        }
                        if !items.is_empty()
                        {
                            let count = items.len();
                            if !emit(&events, WorkerEvent::Events(items))
                                || !emit(&events, WorkerEvent::Log(format!("received {count} event(s)")))
                            {
                                return;
                            }
                        }
                    }
                    Err(error) =>
                    {
                        connected = false;
                        failure_reported = true;
                        if !emit(&events, WorkerEvent::Connection(false))
                            || !emit(&events, WorkerEvent::Failure(error.to_string()))
                        {
                            return;
                        }
                    }
                }
                ticks = ticks.wrapping_add(1);
                if connected && ticks % HEALTH_REFRESH_TICKS == 0
                {
                    if let Ok(snapshot) = fetch_snapshot(&client).await
                        && !emit(&events, WorkerEvent::Snapshot(snapshot))
                    {
                        return;
                    }
                    match fetch_health(&client).await
                    {
                        Ok(health) =>
                        {
                            if !emit(&events, WorkerEvent::Health(health))
                            {
                                return;
                            }
                        }
                        Err(error) =>
                        {
                            if !emit(
                                &events,
                                WorkerEvent::Log(format!("health refresh failed: {error}")),
                            )
                            {
                                return;
                            }
                        }
                    }
                }
            }
        }
    }
}

async fn send_command(client: &ControlClient, command: WorkerCommand) -> Result<(), AppError>
{
    let command = match command
    {
        WorkerCommand::Submit(text) => ControlCommand::Submit { text },
        WorkerCommand::Interrupt => ControlCommand::Interrupt {
            reason: "desktop user interrupt".to_owned(),
        },
        WorkerCommand::EmergencyStop => ControlCommand::EmergencyStop,
    };
    match client.send(command).await?
    {
        ControlPayload::Accepted => Ok(()),
        _ => Err(AppError::protocol("control command returned an unexpected payload")),
    }
}

async fn fetch_snapshot(client: &ControlClient) -> Result<RuntimeSnapshot, AppError>
{
    match client.send(ControlCommand::Status).await?
    {
        ControlPayload::Snapshot(snapshot) => Ok(snapshot),
        _ => Err(AppError::protocol("status returned an unexpected payload")),
    }
}

async fn fetch_health(client: &ControlClient) -> Result<Vec<ComponentHealth>, AppError>
{
    match client.send(ControlCommand::Health).await?
    {
        ControlPayload::Health(health) => Ok(health),
        _ => Err(AppError::protocol("health returned an unexpected payload")),
    }
}

async fn poll(client: &ControlClient, after: u64) -> Result<Vec<SequencedEvent>, AppError>
{
    match client
        .send(ControlCommand::Events {
            after,
            limit: 256,
        })
        .await?
    {
        ControlPayload::Events(events) => Ok(events),
        _ => Err(AppError::protocol("events returned an unexpected payload")),
    }
}

fn emit(sender: &Sender<WorkerEvent>, event: WorkerEvent) -> bool
{
    sender.send(event).is_ok()
}

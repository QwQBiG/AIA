#![forbid(unsafe_code)]

use std::path::PathBuf;

use ai_ex_event_bus::{load_jsonl, replay_delay, EventBus, EventPolicy, PublishOutcome};
use ai_ex_domain::AppError;

#[tokio::main]
async fn main()
{
    if let Err(error) = run().await
    {
        eprintln!("AIex simulator failed: {error}");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), AppError>
{
    let (path, speed) = parse_args(std::env::args().skip(1))?;
    let events = load_jsonl(&path)?;
    let (mut bus, mut receiver) = EventBus::new(EventPolicy::default());
    let mut previous = None;
    let mut accepted = 0_usize;
    for event in events
    {
        if let Some(previous_ms) = previous
        {
            tokio::time::sleep(replay_delay(previous_ms, event.timestamp_ms, speed)).await;
        }
        let priority = event.payload.priority();
        let outcome = bus.publish(event.clone());
        if outcome == PublishOutcome::Accepted
        {
            accepted += 1;
            if let Ok(delivered) = receiver.try_recv()
            {
                println!(
                    "accepted priority={priority:?} type={} payload={}",
                    event_type(&delivered.payload),
                    serde_json::to_string(&delivered.payload).unwrap_or_default(),
                );
            }
        }
        else
        {
            println!("filtered outcome={outcome:?} type={}", event_type(&event.payload));
        }
        previous = Some(event.timestamp_ms);
    }
    println!("simulation complete: accepted={accepted}");
    Ok(())
}

fn parse_args(arguments: impl Iterator<Item = String>) -> Result<(PathBuf, f64), AppError>
{
    let mut input = None;
    let mut speed = 1.0;
    let mut arguments = arguments;
    while let Some(argument) = arguments.next()
    {
        match argument.as_str()
        {
            "--input" =>
            {
                input = Some(PathBuf::from(arguments.next().ok_or_else(|| {
                    AppError::configuration("--input requires a JSONL path")
                })?));
            }
            "--speed" =>
            {
                let value = arguments
                    .next()
                    .ok_or_else(|| AppError::configuration("--speed requires a number"))?;
                speed = value
                    .parse::<f64>()
                    .map_err(|_| AppError::configuration("--speed must be a positive number"))?;
                if !speed.is_finite() || speed <= 0.0
                {
                    return Err(AppError::configuration("--speed must be a positive number"));
                }
            }
            "--help" | "-h" =>
            {
                return Err(AppError::configuration(
                    "usage: ai-ex-simulator --input PATH [--speed N]",
                ));
            }
            _ => return Err(AppError::configuration(format!("unknown argument: {argument}"))),
        }
    }
    let input = input.ok_or_else(|| AppError::configuration("--input is required"))?;
    Ok((input, speed))
}

fn event_type(event: &ai_ex_event_bus::LiveEvent) -> &'static str
{
    match event
    {
        ai_ex_event_bus::LiveEvent::ChatMessage { .. } => "chat_message",
        ai_ex_event_bus::LiveEvent::Follow { .. } => "follow",
        ai_ex_event_bus::LiveEvent::Subscription { .. } => "subscription",
        ai_ex_event_bus::LiveEvent::Gift { .. } => "gift",
        ai_ex_event_bus::LiveEvent::Donation { .. } => "donation",
        ai_ex_event_bus::LiveEvent::Mention { .. } => "mention",
        ai_ex_event_bus::LiveEvent::Moderation { .. } => "moderation",
        ai_ex_event_bus::LiveEvent::Timer { .. } => "timer",
        ai_ex_event_bus::LiveEvent::GameObservation { .. } => "game_observation",
        ai_ex_event_bus::LiveEvent::SystemNotice { .. } => "system_notice",
    }
}

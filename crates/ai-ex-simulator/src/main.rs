#![forbid(unsafe_code)]

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::PathBuf;

use ai_ex_event_bus::{load_jsonl, project_memory, replay_delay, EventBus, EventPolicy, PublishOutcome};
use ai_ex_domain::AppError;
use ai_ex_memory::MemoryStore;
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
struct SimulationRecord
{
    event_id: String,
    timestamp_ms: u64,
    event_type: String,
    priority: String,
    outcome: String,
    reaction_prompt: Option<String>,
    memory_projections: usize,
}

struct SimulationOptions
{
    input: PathBuf,
    speed: f64,
    memory_path: Option<PathBuf>,
    report_path: Option<PathBuf>,
}
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
    let options = parse_args(std::env::args().skip(1))?;
    let mut memory = match options.memory_path
    {
        Some(path) => Some(MemoryStore::open(path).await?),
        None => None,
    };
    let mut report = options
        .report_path
        .as_ref()
        .map(|path| {
            File::create(path)
                .map(BufWriter::new)
                .map_err(|error| AppError::unavailable(format!("cannot create simulation report: {error}")))
        })
        .transpose()?;
    let events = load_jsonl(&options.input)?;
    let (mut bus, mut receiver) = EventBus::new(EventPolicy::default());
    let mut previous = None;
    let mut accepted = 0_usize;
    let mut filtered = 0_usize;
    let mut reaction_suggestions = 0_usize;
    let mut persisted = 0_usize;
    for event in events
    {
        if let Some(previous_ms) = previous
        {
            tokio::time::sleep(replay_delay(previous_ms, event.timestamp_ms, options.speed)).await;
        }
        let event_id = event.event_id.to_string();
        let timestamp_ms = event.timestamp_ms;
        let priority = event.payload.priority();
        let outcome = bus.publish(event.clone());
        let (event_type, reaction_prompt, memory_projections) = if outcome == PublishOutcome::Accepted
        {
            accepted += 1;
            if let Ok(delivered) = receiver.try_recv()
            {
                let reaction_prompt = delivered.payload.reaction_prompt();
                if reaction_prompt.is_some()
                {
                    reaction_suggestions += 1;
                }
                let projections = project_memory(&delivered);
                let projection_count = projections.len();
                if let Some(memory) = memory.as_mut()
                {
                    for projection in projections
                    {
                        memory.remember_projection(&projection).await?;
                        persisted += 1;
                    }
                }
                println!(
                    "accepted priority={priority:?} type={} response_suggested={} payload={}",
                    event_type(&delivered.payload),
                    reaction_prompt.is_some(),
                    serde_json::to_string(&delivered.payload).unwrap_or_default(),
                );
                (
                    event_type(&delivered.payload).to_owned(),
                    reaction_prompt,
                    projection_count,
                )
            }
            else
            {
                (event_type(&event.payload).to_owned(), None, 0)
            }
        }
        else
        {
            filtered += 1;
            println!("filtered outcome={outcome:?} type={}", event_type(&event.payload));
            (event_type(&event.payload).to_owned(), None, 0)
        };
        if let Some(writer) = report.as_mut()
        {
            let record = SimulationRecord {
                event_id,
                timestamp_ms,
                event_type,
                priority: format!("{priority:?}"),
                outcome: format!("{outcome:?}"),
                reaction_prompt,
                memory_projections,
            };
            serde_json::to_writer(&mut *writer, &record)
                .map_err(|error| AppError::protocol(format!("cannot encode simulation report: {error}")))?;
            writer
                .write_all(b"\n")
                .map_err(|error| AppError::unavailable(format!("cannot write simulation report: {error}")))?;
        }
        previous = Some(timestamp_ms);
    }
    if let Some(writer) = report.as_mut()
    {
        writer
            .flush()
            .map_err(|error| AppError::unavailable(format!("cannot flush simulation report: {error}")))?;
    }
    println!(
        "simulation complete: accepted={accepted} filtered={filtered} response_suggestions={reaction_suggestions} persisted_memory={persisted} report={}",
        options
            .report_path
            .as_ref()
            .map_or_else(|| "none".to_owned(), |path| path.display().to_string()),
    );
    Ok(())
}
fn parse_args(arguments: impl Iterator<Item = String>) -> Result<SimulationOptions, AppError>
{
    let mut input = None;
    let mut speed = 1.0;
    let mut memory_path = None;
    let mut report_path = None;
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
            "--memory" =>
            {
                memory_path = Some(PathBuf::from(arguments.next().ok_or_else(|| {
                    AppError::configuration("--memory requires a JSONL path")
                })?));
            }
            "--report" =>
            {
                report_path = Some(PathBuf::from(arguments.next().ok_or_else(|| {
                    AppError::configuration("--report requires a JSONL path")
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
                    "usage: ai-ex-simulator --input PATH [--speed N] [--memory PATH] [--report PATH]",
                ));
            }
            _ => return Err(AppError::configuration(format!("unknown argument: {argument}"))),
        }
    }
    let input = input.ok_or_else(|| AppError::configuration("--input is required"))?;
    Ok(SimulationOptions {
        input,
        speed,
        memory_path,
        report_path,
    })
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

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn parses_optional_memory_output()
    {
        let args = parse_args([
            "--input".to_owned(),
            "events.jsonl".to_owned(),
            "--memory".to_owned(),
            "memory.jsonl".to_owned(),
            "--speed".to_owned(),
            "10".to_owned(),
            "--report".to_owned(),
            "report.jsonl".to_owned(),
        ].into_iter())
        .expect("simulator arguments parse");
        assert_eq!(args.input, PathBuf::from("events.jsonl"));
        assert_eq!(args.speed, 10.0);
        assert_eq!(args.memory_path, Some(PathBuf::from("memory.jsonl")));
        assert_eq!(args.report_path, Some(PathBuf::from("report.jsonl")));
    }

    #[test]
    fn rejects_missing_memory_path()
    {
        assert!(parse_args(["--input".to_owned(), "events.jsonl".to_owned(), "--memory".to_owned()].into_iter()).is_err());
    }
}

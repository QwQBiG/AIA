use ai_ex_core::EventSink;
use ai_ex_domain::SystemEvent;
use async_trait::async_trait;

#[derive(Debug, Default)]
pub struct ConsoleEvents;

#[async_trait]
impl EventSink for ConsoleEvents
{
    async fn publish(&mut self, event: SystemEvent)
    {
        match &event
        {
            SystemEvent::ModelChunk { text, .. } => print!("{text}"),
            SystemEvent::TurnFinished { .. } => println!(),
            SystemEvent::Fault { message } => eprintln!("runtime fault: {message}"),
            _ =>
            {
            }
        }
        tracing::debug!(event = %serde_json::to_string(&event).unwrap_or_default());
    }
}

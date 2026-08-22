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
            SystemEvent::LiveEventReceived {
                event_type,
                summary,
                ..
            } => tracing::info!(event_type, summary, "live event accepted"),
            SystemEvent::LiveResponseSuggested { automatic, .. } =>
            {
                tracing::info!(automatic, "live reaction suggestion emitted");
            }
            SystemEvent::ComponentHealthChanged {
                component,
                ready,
                detail,
            } => tracing::info!(component, ready, detail, "component health changed"),
            _ =>
            {
            }
        }
        tracing::debug!(event = %serde_json::to_string(&event).unwrap_or_default());
    }
}

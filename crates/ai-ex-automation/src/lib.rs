#![forbid(unsafe_code)]

mod coordinator;
mod dry_run;
mod ports;
mod replay;
mod types;

pub use coordinator::AutomationCoordinator;
pub use dry_run::DryRunAutomationPort;
pub use ports::{AuditSink, AutomationPort};
pub use replay::{AutomationReplayRecord, AUTOMATION_SCHEMA_VERSION, parse_jsonl};
pub use types::{
    ActionResult, AuditRecord, AuditStage, AutomationAction, ExecutionFailure, ExecutionPhase,
    ExecutionReceipt, PointerButton, ScreenFrame,
};

#[cfg(test)]
mod tests;

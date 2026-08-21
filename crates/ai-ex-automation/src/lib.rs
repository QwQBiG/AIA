#![forbid(unsafe_code)]

mod coordinator;
mod dry_run;
mod ports;
mod plugin_protocol;
mod replay;
mod types;

pub use coordinator::AutomationCoordinator;
pub use dry_run::DryRunAutomationPort;
pub use ports::{AuditSink, AutomationPort};
pub use plugin_protocol::{AutomationPluginRequest, AutomationPluginRequestKind, AutomationPluginResponse, AutomationPluginResponseKind, AUTOMATION_PLUGIN_SCHEMA_VERSION};
pub use replay::{AutomationReplayRecord, AUTOMATION_SCHEMA_VERSION, parse_jsonl};
pub use types::{
    ActionResult, AuditRecord, AuditStage, AutomationAction, ExecutionFailure, ExecutionPhase,
    ExecutionReceipt, PointerButton, ScreenFrame,
};

#[cfg(test)]
mod tests;

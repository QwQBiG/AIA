#![forbid(unsafe_code)]

mod coordinator;
mod dry_run;
mod plugin_port;
mod plugin_protocol;
mod ports;
mod replay;
mod types;

pub use coordinator::AutomationCoordinator;
pub use dry_run::DryRunAutomationPort;
pub use plugin_port::{AutomationPluginTransport, PluginAutomationPort};
pub use plugin_protocol::{
    AUTOMATION_PLUGIN_SCHEMA_VERSION, AutomationPluginRequest, AutomationPluginRequestKind,
    AutomationPluginResponse, AutomationPluginResponseKind,
};
pub use ports::{AuditSink, AutomationPort};
pub use replay::{AUTOMATION_SCHEMA_VERSION, AutomationReplayRecord, parse_jsonl};
pub use types::{
    ActionResult, AuditRecord, AuditStage, AutomationAction, ExecutionFailure, ExecutionPhase,
    ExecutionReceipt, PointerButton, ScreenFrame,
};

#[cfg(test)]
mod tests;

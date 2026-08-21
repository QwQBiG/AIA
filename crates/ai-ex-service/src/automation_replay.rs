#![forbid(unsafe_code)]

use std::collections::BTreeSet;
use std::path::Path;
use std::sync::Arc;

use ai_ex_audit::JsonlAuditLog;
use ai_ex_automation::{
    ActionResult, AutomationCoordinator, AutomationReplayRecord, DryRunAutomationPort, parse_jsonl,
};
use ai_ex_config::AppConfig;
use ai_ex_domain::AppError;
use ai_ex_safety::{Capability, SafetyGate, SafetyPolicy};

pub async fn replay(path: &Path, config: &AppConfig) -> Result<(), AppError>
{
    let input = tokio::fs::read_to_string(path).await.map_err(|error| {
        AppError::unavailable(format!(
            "cannot read automation replay {}: {error}",
            path.display(),
        ))
    })?;
    let records = parse_jsonl(&input)?;
    let (capabilities, targets) = policy_scope(&records);
    let safety = Arc::new(SafetyGate::new(SafetyPolicy {
        automation_enabled: true,
        allowed_capabilities: capabilities,
        allowed_targets: targets,
    }));
    let audit = JsonlAuditLog::open(&config.safety.audit_path).await?;
    let mut coordinator = AutomationCoordinator::new(
        safety,
        DryRunAutomationPort::new(4_096, 640, 360)?,
        audit,
    );
    let mut screenshots = 0_usize;
    for record in records.iter().cloned()
    {
        let receipt = coordinator
            .execute(record.target, record.rationale, record.action)
            .await
            .map_err(|failure| failure.error)?;
        if matches!(receipt.result, ActionResult::ScreenCaptured(_))
        {
            screenshots += 1;
        }
    }
    println!(
        "automation dry-run replay complete: records={}, screenshots={}, mode=dry_run",
        records.len(),
        screenshots,
    );
    Ok(())
}

fn policy_scope(records: &[AutomationReplayRecord]) -> (BTreeSet<Capability>, Vec<String>)
{
    let mut capabilities = BTreeSet::new();
    let mut targets = Vec::new();
    for record in records
    {
        capabilities.insert(record.action.required_capability());
        if !targets.iter().any(|target| target == &record.target)
        {
            targets.push(record.target.clone());
        }
    }
    (capabilities, targets)
}

use std::collections::BTreeSet;
use std::sync::{Arc, Mutex};

use ai_ex_domain::AppError;
use ai_ex_safety::{Capability, Permit, SafetyGate, SafetyPolicy};
use async_trait::async_trait;

use super::*;

struct MockPort
{
    calls: Arc<Mutex<usize>>,
    fail: bool,
}

#[async_trait]
impl AutomationPort for MockPort
{
    async fn execute(
        &mut self,
        permit: &Permit,
        _action: &AutomationAction,
    ) -> Result<ActionResult, AppError>
    {
        permit.ensure_active()?;
        *self.calls.lock().unwrap() += 1;
        if self.fail
        {
            Err(AppError::unavailable("adapter failed"))
        }
        else
        {
            Ok(ActionResult::Completed)
        }
    }
}

struct RecordingAudit
{
    records: Arc<Mutex<Vec<AuditRecord>>>,
    stop_after_authorize: Option<Arc<SafetyGate>>,
}

#[async_trait]
impl AuditSink for RecordingAudit
{
    async fn record(&mut self, record: AuditRecord) -> Result<(), AppError>
    {
        if record.stage == AuditStage::Authorized
            && let Some(gate) = &self.stop_after_authorize
        {
            gate.trigger_emergency_stop();
        }
        self.records.lock().unwrap().push(record);
        Ok(())
    }
}

fn gate() -> Arc<SafetyGate>
{
    Arc::new(SafetyGate::new(SafetyPolicy {
        automation_enabled: true,
        allowed_capabilities: BTreeSet::from([
            Capability::KeyboardInput,
            Capability::ScreenRead,
        ]),
        allowed_targets: vec!["game".to_owned()],
    }))
}

struct Harness
{
    coordinator: AutomationCoordinator<MockPort, RecordingAudit>,
    calls: Arc<Mutex<usize>>,
    records: Arc<Mutex<Vec<AuditRecord>>>,
}

fn coordinator(
    gate: Arc<SafetyGate>,
    fail: bool,
    stop_after_authorize: bool,
) -> Harness
{
    let calls = Arc::new(Mutex::new(0));
    let records = Arc::new(Mutex::new(Vec::new()));
    let coordinator = AutomationCoordinator::new(
        Arc::clone(&gate),
        MockPort {
            calls: Arc::clone(&calls),
            fail,
        },
        RecordingAudit {
            records: Arc::clone(&records),
            stop_after_authorize: stop_after_authorize.then_some(gate),
        },
    );
    Harness {
        coordinator,
        calls,
        records,
    }
}

#[tokio::test]
async fn executes_with_durable_pre_audit_and_redacts_typed_text()
{
    let mut harness = coordinator(gate(), false, false);
    let receipt = harness
        .coordinator
        .execute(
            "game",
            "reply in chat",
            AutomationAction::TypeText {
                text: "private message".to_owned(),
            },
        )
        .await
        .expect("action succeeds");

    assert!(receipt.completion_audit_persisted);
    assert_eq!(*harness.calls.lock().unwrap(), 1);
    let records = harness.records.lock().unwrap();
    assert_eq!(records.len(), 3);
    assert_eq!(records[0].stage, AuditStage::Requested);
    assert_eq!(records[1].stage, AuditStage::Authorized);
    assert_eq!(records[2].stage, AuditStage::Completed);
    assert!(records.iter().all(|record| !record.action.contains("private message")));
}

#[tokio::test]
async fn emergency_stop_between_authorization_and_execution_is_fail_closed()
{
    let gate = gate();
    let mut harness = coordinator(gate, false, true);
    let failure = harness
        .coordinator
        .execute("game", "inspect", AutomationAction::CaptureScreen)
        .await
        .expect_err("emergency stop rejects action");

    assert_eq!(failure.phase, ExecutionPhase::BeforeExecution);
    assert_eq!(*harness.calls.lock().unwrap(), 0);
    assert_eq!(
        harness.records.lock().unwrap().last().unwrap().stage,
        AuditStage::Rejected,
    );
}

#[tokio::test]
async fn adapter_failure_is_not_marked_safe_to_retry()
{
    let mut harness = coordinator(gate(), true, false);
    let failure = harness
        .coordinator
        .execute(
            "game",
            "reply",
            AutomationAction::TypeText {
                text: "hello".to_owned(),
            },
        )
        .await
        .expect_err("adapter fails");

    assert_eq!(failure.phase, ExecutionPhase::DuringExecution);
    assert!(!failure.retry_is_safe());
    assert_eq!(*harness.calls.lock().unwrap(), 1);
}

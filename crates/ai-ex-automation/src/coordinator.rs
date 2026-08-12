use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use ai_ex_domain::AppError;
use ai_ex_safety::{ActionRequest, Capability, SafetyGate};
use uuid::Uuid;

use crate::{
    AuditRecord, AuditSink, AuditStage, AutomationAction, AutomationPort, ExecutionFailure,
    ExecutionPhase, ExecutionReceipt,
};

pub struct AutomationCoordinator<P, A>
{
    safety: Arc<SafetyGate>,
    port: P,
    audit: A,
}

impl<P, A> AutomationCoordinator<P, A>
where
    P: AutomationPort,
    A: AuditSink,
{
    pub fn new(safety: Arc<SafetyGate>, port: P, audit: A) -> Self
    {
        Self {
            safety,
            port,
            audit,
        }
    }

    pub async fn execute(
        &mut self,
        target: impl Into<String>,
        rationale: impl Into<String>,
        action: AutomationAction,
    ) -> Result<ExecutionReceipt, ExecutionFailure>
    {
        let action_id = Uuid::new_v4();
        let target = target.into();
        let rationale = rationale.into();
        let capability = action.required_capability();
        let label = action.audit_label();
        if let Err(error) = action.validate()
        {
            let _ignored = self
                .record(action_id, AuditStage::Rejected, capability, &target, &label, &error.message)
                .await;
            return Err(failure(action_id, ExecutionPhase::BeforeExecution, error));
        }
        if let Err(error) = self
            .record(action_id, AuditStage::Requested, capability, &target, &label, &rationale)
            .await
        {
            return Err(failure(action_id, ExecutionPhase::BeforeExecution, error));
        }
        let permit = match self.safety.authorize(ActionRequest {
            capability,
            target: target.clone(),
            rationale,
        })
        {
            Ok(permit) => permit,
            Err(error) =>
            {
                let _ignored = self
                    .record(
                        action_id,
                        AuditStage::Rejected,
                        capability,
                        &target,
                        &label,
                        &error.message,
                    )
                    .await;
                return Err(failure(action_id, ExecutionPhase::BeforeExecution, error));
            }
        };
        if let Err(error) = self
            .record(
                action_id,
                AuditStage::Authorized,
                capability,
                &target,
                &label,
                "permit granted",
            )
            .await
        {
            return Err(failure(action_id, ExecutionPhase::BeforeExecution, error));
        }
        if let Err(error) = permit.ensure_active()
        {
            let _ignored = self
                .record(
                    action_id,
                    AuditStage::Rejected,
                    capability,
                    &target,
                    &label,
                    &error.message,
                )
                .await;
            return Err(failure(action_id, ExecutionPhase::BeforeExecution, error));
        }
        let result = match self.port.execute(&permit, &action).await
        {
            Ok(result) => result,
            Err(error) =>
            {
                let _ignored = self
                    .record(
                        action_id,
                        AuditStage::Failed,
                        capability,
                        &target,
                        &label,
                        &error.message,
                    )
                    .await;
                return Err(failure(action_id, ExecutionPhase::DuringExecution, error));
            }
        };
        let completion_audit_persisted = self
            .record(
                action_id,
                AuditStage::Completed,
                capability,
                &target,
                &label,
                "completed",
            )
            .await
            .is_ok();
        Ok(ExecutionReceipt {
            action_id,
            result,
            completion_audit_persisted,
        })
    }

    async fn record(
        &mut self,
        action_id: Uuid,
        stage: AuditStage,
        capability: Capability,
        target: &str,
        action: &str,
        detail: &str,
    ) -> Result<(), AppError>
    {
        self.audit
            .record(AuditRecord {
                action_id,
                timestamp_ms: timestamp_ms(),
                stage,
                capability,
                target: target.to_owned(),
                action: action.to_owned(),
                detail: detail.to_owned(),
            })
            .await
    }
}

fn failure(action_id: Uuid, phase: ExecutionPhase, error: AppError) -> ExecutionFailure
{
    ExecutionFailure {
        action_id,
        phase,
        error,
    }
}

fn timestamp_ms() -> u64
{
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |duration| duration.as_millis().min(u128::from(u64::MAX)) as u64)
}

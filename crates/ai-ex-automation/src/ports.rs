use ai_ex_domain::AppError;
use ai_ex_safety::Permit;
use async_trait::async_trait;

use crate::{ActionResult, AuditRecord, AutomationAction};

#[async_trait]
pub trait AutomationPort: Send
{
    async fn execute(
        &mut self,
        permit: &Permit,
        action: &AutomationAction,
    ) -> Result<ActionResult, AppError>;
}

#[async_trait]
pub trait AuditSink: Send
{
    async fn record(&mut self, record: AuditRecord) -> Result<(), AppError>;
}

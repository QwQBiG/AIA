#![forbid(unsafe_code)]

use ai_ex_domain::AppError;
use ai_ex_safety::Permit;
use async_trait::async_trait;

use crate::{
    ActionResult, AutomationAction, AutomationPluginRequest, AutomationPluginRequestKind,
    AutomationPluginResponse, AutomationPluginResponseKind, AutomationPort,
};

#[async_trait]
pub trait AutomationPluginTransport: Send
{
    async fn call(
        &mut self,
        request: AutomationPluginRequest,
    ) -> Result<AutomationPluginResponse, AppError>;
}

pub struct PluginAutomationPort<T>
{
    transport: T,
}

impl<T> PluginAutomationPort<T>
{
    pub fn new(transport: T) -> Self
    {
        Self { transport }
    }

    pub async fn observe(&mut self, prompt: impl Into<String>) -> Result<AutomationPluginResponse, AppError>
    where
        T: AutomationPluginTransport,
    {
        self.call(AutomationPluginRequest::new(AutomationPluginRequestKind::Observe {
            prompt: prompt.into(),
        }))
        .await
    }

    pub async fn interrupt(&mut self) -> Result<(), AppError>
    where
        T: AutomationPluginTransport,
    {
        let response = self
            .call(AutomationPluginRequest::new(AutomationPluginRequestKind::Interrupt))
            .await?;
        if matches!(response.payload, AutomationPluginResponseKind::Interrupted)
        {
            Ok(())
        }
        else
        {
            Err(AppError::protocol("automation plugin interrupt response is invalid"))
        }
    }

    async fn call(
        &mut self,
        request: AutomationPluginRequest,
    ) -> Result<AutomationPluginResponse, AppError>
    where
        T: AutomationPluginTransport,
    {
        request.validate()?;
        let response = self.transport.call(request.clone()).await?;
        response.validate()?;
        if response.request_id != request.request_id
        {
            return Err(AppError::protocol(
                "automation plugin response request ID mismatch",
            ));
        }
        Ok(response)
    }
}

#[async_trait]
impl<T> AutomationPort for PluginAutomationPort<T>
where
    T: AutomationPluginTransport,
{
    async fn execute(
        &mut self,
        permit: &Permit,
        action: &AutomationAction,
    ) -> Result<ActionResult, AppError>
    {
        permit.ensure_active()?;
        action.validate()?;
        if permit.capability() != action.required_capability()
        {
            return Err(AppError::safety(
                "automation permit capability does not match action",
            ));
        }
        let response = self
            .call(AutomationPluginRequest::new(AutomationPluginRequestKind::Execute {
                target: permit.target().to_owned(),
                rationale: permit.rationale().to_owned(),
                action: action.clone(),
            }))
            .await?;
        match response.payload
        {
            AutomationPluginResponseKind::ActionAccepted { .. }
            | AutomationPluginResponseKind::Observation { .. } => Ok(ActionResult::Completed),
            AutomationPluginResponseKind::Interrupted => Err(AppError::protocol(
                "automation plugin interrupted an execute request",
            )),
        }
    }
}

#[cfg(test)]
mod tests
{
    use std::collections::BTreeSet;

    use ai_ex_safety::{ActionRequest, Capability, SafetyGate, SafetyPolicy};
    use uuid::Uuid;

    use super::*;

    use crate::AUTOMATION_PLUGIN_SCHEMA_VERSION;
    struct FakeTransport
    {
        response: Option<AutomationPluginResponse>,
    }

    #[async_trait]
    impl AutomationPluginTransport for FakeTransport
    {
        async fn call(
            &mut self,
            request: AutomationPluginRequest,
        ) -> Result<AutomationPluginResponse, AppError>
        {
            let mut response = self.response.take().expect("fake response configured");
            response.request_id = request.request_id;
            Ok(response)
        }
    }

    fn permit() -> Permit
    {
        SafetyGate::new(SafetyPolicy {
            automation_enabled: true,
            allowed_capabilities: BTreeSet::from([Capability::MouseInput]),
            allowed_targets: vec!["game".to_owned()],
        })
        .authorize(ActionRequest {
            capability: Capability::MouseInput,
            target: "game".to_owned(),
            rationale: "test action".to_owned(),
        })
        .expect("permit authorizes")
    }

    #[tokio::test]
    async fn executes_typed_request_after_safety_validation()
    {
        let transport = FakeTransport {
            response: Some(AutomationPluginResponse {
                schema_version: AUTOMATION_PLUGIN_SCHEMA_VERSION,
                request_id: Uuid::nil(),
                payload: AutomationPluginResponseKind::ActionAccepted {
                    action_id: Uuid::new_v4(),
                },
            }),
        };
        let mut port = PluginAutomationPort::new(transport);
        let result = port
            .execute(
                &permit(),
                &AutomationAction::Click {
                    button: crate::PointerButton::Left,
                },
            )
            .await
            .expect("plugin action executes");
        assert_eq!(result, ActionResult::Completed);
    }

    #[tokio::test]
    async fn rejects_wrong_response_request_id()
    {
        struct MismatchTransport;

        #[async_trait]
        impl AutomationPluginTransport for MismatchTransport
        {
            async fn call(
                &mut self,
                _request: AutomationPluginRequest,
            ) -> Result<AutomationPluginResponse, AppError>
            {
                Ok(AutomationPluginResponse {
                    schema_version: AUTOMATION_PLUGIN_SCHEMA_VERSION,
                    request_id: Uuid::nil(),
                    payload: AutomationPluginResponseKind::Interrupted,
                })
            }
        }

        let mut port = PluginAutomationPort::new(MismatchTransport);
        let error = port
            .execute(
                &permit(),
                &AutomationAction::Click {
                    button: crate::PointerButton::Left,
                },
            )
            .await
            .expect_err("mismatched response is rejected");
        assert_eq!(error.kind, ai_ex_domain::ErrorKind::Protocol);
    }
}
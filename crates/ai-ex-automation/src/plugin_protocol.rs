#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use ai_ex_domain::AppError;

use crate::AutomationAction;

pub const AUTOMATION_PLUGIN_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AutomationPluginRequest
{
    pub schema_version: u16,
    pub request_id: Uuid,
    #[serde(flatten)]
    pub payload: AutomationPluginRequestKind,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum AutomationPluginRequestKind
{
    Observe { prompt: String },
    Execute {
        target: String,
        rationale: String,
        action: AutomationAction,
    },
    Interrupt,
}

impl AutomationPluginRequest
{
    pub fn new(payload: AutomationPluginRequestKind) -> Self
    {
        Self {
            schema_version: AUTOMATION_PLUGIN_SCHEMA_VERSION,
            request_id: Uuid::new_v4(),
            payload,
        }
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.schema_version != AUTOMATION_PLUGIN_SCHEMA_VERSION
        {
            return Err(AppError::protocol(format!(
                "unsupported automation plugin schema version {}",
                self.schema_version,
            )));
        }
        match &self.payload
        {
            AutomationPluginRequestKind::Observe { prompt }
                if prompt.chars().count() > 4_096 =>
            {
                Err(AppError::configuration(
                    "automation observe prompt is too long",
                ))
            }
            AutomationPluginRequestKind::Execute {
                target,
                rationale,
                action,
            } =>
            {
                if target.trim().is_empty() || target.chars().count() > 256
                {
                    return Err(AppError::configuration(
                        "automation plugin target is invalid",
                    ));
                }
                if rationale.trim().is_empty() || rationale.chars().count() > 4_096
                {
                    return Err(AppError::configuration(
                        "automation plugin rationale is invalid",
                    ));
                }
                action.validate()
            }
            AutomationPluginRequestKind::Interrupt => Ok(()),
            _ => Ok(()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AutomationPluginResponse
{
    pub schema_version: u16,
    pub request_id: Uuid,
    #[serde(flatten)]
    pub payload: AutomationPluginResponseKind,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum AutomationPluginResponseKind
{
    Observation {
        source: String,
        summary: String,
        frame_ref: Option<String>,
        confidence: Option<f32>,
    },
    ActionAccepted { action_id: Uuid },
    Interrupted,
}

impl AutomationPluginResponse
{
    pub fn observation(
        request_id: Uuid,
        source: impl Into<String>,
        summary: impl Into<String>,
        frame_ref: Option<String>,
        confidence: Option<f32>,
    ) -> Self
    {
        Self {
            schema_version: AUTOMATION_PLUGIN_SCHEMA_VERSION,
            request_id,
            payload: AutomationPluginResponseKind::Observation {
                source: source.into(),
                summary: summary.into(),
                frame_ref,
                confidence,
            },
        }
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.schema_version != AUTOMATION_PLUGIN_SCHEMA_VERSION
        {
            return Err(AppError::protocol(format!(
                "unsupported automation plugin schema version {}",
                self.schema_version,
            )));
        }
        if let AutomationPluginResponseKind::Observation
        {
            source,
            summary,
            frame_ref,
            confidence,
        } = &self.payload
        {
            if source.trim().is_empty() || source.chars().count() > 256
            {
                return Err(AppError::protocol(
                    "automation observation source is invalid",
                ));
            }
            if summary.trim().is_empty() || summary.chars().count() > 8_192
            {
                return Err(AppError::protocol(
                    "automation observation summary is invalid",
                ));
            }
            if frame_ref
                .as_deref()
                .is_some_and(|value| value.trim().is_empty() || value.chars().count() > 2_048)
            {
                return Err(AppError::protocol(
                    "automation observation frame reference is invalid",
                ));
            }
            if confidence.is_some_and(|value| !value.is_finite() || !(0.0..=1.0).contains(&value))
            {
                return Err(AppError::protocol(
                    "automation observation confidence must be between 0 and 1",
                ));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn request_round_trips_an_execute_action()
    {
        let request = AutomationPluginRequest::new(AutomationPluginRequestKind::Execute {
            target: "game".to_owned(),
            rationale: "demo".to_owned(),
            action: AutomationAction::CaptureScreen,
        });
        let encoded = serde_json::to_string(&request).expect("request encodes");
        let decoded: AutomationPluginRequest =
            serde_json::from_str(&encoded).expect("request decodes");
        decoded.validate().expect("request validates");
        assert_eq!(decoded, request);
    }

    #[test]
    fn response_rejects_invalid_confidence()
    {
        let response = AutomationPluginResponse::observation(
            Uuid::new_v4(),
            "vision",
            "screen",
            None,
            Some(1.5),
        );
        assert!(response.validate().is_err());
    }

    #[test]
    fn observe_prompt_has_a_bound()
    {
        let request = AutomationPluginRequest::new(AutomationPluginRequestKind::Observe {
            prompt: "x".repeat(4_097),
        });
        assert!(request.validate().is_err());
    }
}

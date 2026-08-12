#![forbid(unsafe_code)]

use std::collections::BTreeSet;
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};

use ai_ex_domain::{AppError, ComponentHealth};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Capability
{
    ScreenRead,
    MouseInput,
    KeyboardInput,
    ProcessLaunch,
}

impl std::str::FromStr for Capability
{
    type Err = AppError;

    fn from_str(value: &str) -> Result<Self, Self::Err>
    {
        match value
        {
            "screen_read" => Ok(Self::ScreenRead),
            "mouse_input" => Ok(Self::MouseInput),
            "keyboard_input" => Ok(Self::KeyboardInput),
            "process_launch" => Ok(Self::ProcessLaunch),
            _ => Err(AppError::configuration(format!(
                "unknown automation capability: {value}",
            ))),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActionRequest
{
    pub capability: Capability,
    pub target: String,
    pub rationale: String,
}

#[derive(Debug, Clone)]
pub struct SafetyPolicy
{
    pub automation_enabled: bool,
    pub allowed_capabilities: BTreeSet<Capability>,
    pub allowed_targets: Vec<String>,
}

#[derive(Debug)]
pub struct Permit
{
    id: Uuid,
    capability: Capability,
    target: String,
    emergency_stop: Arc<AtomicBool>,
}

impl Permit
{
    pub fn id(&self) -> Uuid
    {
        self.id
    }

    pub fn capability(&self) -> Capability
    {
        self.capability
    }

    pub fn target(&self) -> &str
    {
        &self.target
    }

    pub fn ensure_active(&self) -> Result<(), AppError>
    {
        if self.emergency_stop.load(Ordering::Acquire)
        {
            return Err(AppError::safety("permit revoked by emergency stop"));
        }
        Ok(())
    }
}

pub struct SafetyGate
{
    policy: SafetyPolicy,
    emergency_stop: Arc<AtomicBool>,
}

impl SafetyGate
{
    pub fn new(policy: SafetyPolicy) -> Self
    {
        Self {
            policy,
            emergency_stop: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn authorize(&self, request: ActionRequest) -> Result<Permit, AppError>
    {
        if self.emergency_stop.load(Ordering::Acquire)
        {
            return Err(AppError::safety("automation emergency stop is active"));
        }
        if !self.policy.automation_enabled
        {
            return Err(AppError::safety("automation is disabled"));
        }
        if !self.policy.allowed_capabilities.contains(&request.capability)
        {
            return Err(AppError::safety("automation capability is not allowed"));
        }
        if request.rationale.trim().is_empty()
        {
            return Err(AppError::safety("automation action requires a rationale"));
        }
        let target = request.target.trim();
        if target.is_empty() || !self.target_allowed(target)
        {
            return Err(AppError::safety("automation target is outside allowed scopes"));
        }
        Ok(Permit {
            id: Uuid::new_v4(),
            capability: request.capability,
            target: target.to_owned(),
            emergency_stop: self.emergency_stop.clone(),
        })
    }

    pub fn trigger_emergency_stop(&self)
    {
        self.emergency_stop.store(true, Ordering::Release);
    }

    pub fn clear_emergency_stop(&mut self)
    {
        self.emergency_stop.store(false, Ordering::Release);
    }

    pub fn emergency_stop_active(&self) -> bool
    {
        self.emergency_stop.load(Ordering::Acquire)
    }

    pub fn health(&self) -> ComponentHealth
    {
        let detail = if self.emergency_stop_active()
        {
            "emergency stop active"
        }
        else if self.policy.automation_enabled
        {
            "automation policy active"
        }
        else
        {
            "automation disabled"
        };
        ComponentHealth {
            component: "safety".to_owned(),
            ready: true,
            detail: detail.to_owned(),
        }
    }

    fn target_allowed(&self, target: &str) -> bool
    {
        self.policy
            .allowed_targets
            .iter()
            .any(|allowed| allowed == target)
    }
}

#[cfg(test)]
mod tests
{
    use ai_ex_domain::ErrorKind;

    use super::*;

    fn policy(enabled: bool) -> SafetyPolicy
    {
        SafetyPolicy {
            automation_enabled: enabled,
            allowed_capabilities: BTreeSet::from([Capability::ScreenRead]),
            allowed_targets: vec!["VTube Studio".to_owned()],
        }
    }

    #[test]
    fn disabled_automation_denies_every_request()
    {
        let gate = SafetyGate::new(policy(false));
        let result = gate.authorize(ActionRequest {
            capability: Capability::ScreenRead,
            target: "VTube Studio".to_owned(),
            rationale: "inspect avatar state".to_owned(),
        });

        assert_eq!(result.unwrap_err().kind, ErrorKind::Safety);
    }

    #[test]
    fn capability_and_target_must_both_be_allowed()
    {
        let gate = SafetyGate::new(policy(true));
        let result = gate.authorize(ActionRequest {
            capability: Capability::MouseInput,
            target: "VTube Studio".to_owned(),
            rationale: "click a control".to_owned(),
        });

        assert!(result.is_err());
    }

    #[test]
    fn emergency_stop_revokes_existing_permits()
    {
        let gate = SafetyGate::new(policy(true));
        let permit = gate
            .authorize(ActionRequest {
                capability: Capability::ScreenRead,
                target: "VTube Studio".to_owned(),
                rationale: "inspect avatar state".to_owned(),
            })
            .expect("authorized request");

        permit.ensure_active().expect("active permit");
        gate.trigger_emergency_stop();
        assert!(permit.ensure_active().is_err());
        assert!(gate.emergency_stop_active());
    }
}

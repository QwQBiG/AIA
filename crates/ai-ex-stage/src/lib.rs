#![forbid(unsafe_code)]

use std::collections::{BTreeSet, VecDeque};

use ai_ex_domain::{AppError, ComponentHealth, Emotion, TurnId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub const STAGE_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum StageAction
{
    Speak {
        turn_id: TurnId,
        text: String,
        interruptible: bool,
    },
    Expression {
        emotion: Emotion,
    },
    Mouth {
        value: f32,
    },
    Subtitle {
        text: String,
        duration_ms: u64,
    },
    Scene {
        scene: String,
    },
    Hotkey {
        id: String,
    },
    Stop,
}

impl StageAction
{
    pub fn kind(&self) -> &'static str
    {
        match self
        {
            Self::Speak { .. } => "speak",
            Self::Expression { .. } => "expression",
            Self::Mouth { .. } => "mouth",
            Self::Subtitle { .. } => "subtitle",
            Self::Scene { .. } => "scene",
            Self::Hotkey { .. } => "hotkey",
            Self::Stop => "stop",
        }
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        match self
        {
            Self::Speak { text, .. } if text.trim().is_empty() =>
            {
                Err(AppError::configuration("stage speak text must not be empty"))
            }
            Self::Speak { text, .. } if text.chars().count() > 4_096 =>
            {
                Err(AppError::configuration("stage speak text is too long"))
            }
            Self::Mouth { value } if !value.is_finite() || !(0.0..=1.0).contains(value) =>
            {
                Err(AppError::configuration("stage mouth value must be between 0 and 1"))
            }
            Self::Subtitle {
                text,
                duration_ms,
            } if text.trim().is_empty() || *duration_ms == 0 =>
            {
                Err(AppError::configuration(
                    "stage subtitle requires text and positive duration",
                ))
            }
            Self::Subtitle { text, .. } if text.chars().count() > 8_192 =>
            {
                Err(AppError::configuration("stage subtitle text is too long"))
            }
            Self::Scene { scene } if scene.trim().is_empty() =>
            {
                Err(AppError::configuration("stage scene must not be empty"))
            }
            Self::Hotkey { id } if id.trim().is_empty() =>
            {
                Err(AppError::configuration("stage hotkey id must not be empty"))
            }
            _ => Ok(()),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StageCapability
{
    Speech,
    Expression,
    Mouth,
    Subtitle,
    Scene,
    Hotkey,
    Interrupt,
}

#[async_trait]
pub trait StageExecutor: Send
{
    fn capabilities(&self) -> BTreeSet<StageCapability>;

    async fn health(&self) -> ComponentHealth;

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>;

    async fn interrupt(&mut self) -> Result<(), AppError>;
}

pub struct DryRunStage
{
    actions: VecDeque<StageAction>,
    capacity: usize,
}

impl DryRunStage
{
    pub fn new(capacity: usize) -> Result<Self, AppError>
    {
        if capacity == 0
        {
            return Err(AppError::configuration("stage dry-run capacity must be positive"));
        }
        Ok(Self {
            actions: VecDeque::with_capacity(capacity),
            capacity,
        })
    }

    pub fn actions(&self) -> impl Iterator<Item = &StageAction>
    {
        self.actions.iter()
    }

    pub fn len(&self) -> usize
    {
        self.actions.len()
    }

    pub fn is_empty(&self) -> bool
    {
        self.actions.is_empty()
    }
}

#[async_trait]
impl StageExecutor for DryRunStage
{
    fn capabilities(&self) -> BTreeSet<StageCapability>
    {
        BTreeSet::from([
            StageCapability::Expression,
            StageCapability::Hotkey,
            StageCapability::Interrupt,
            StageCapability::Mouth,
            StageCapability::Scene,
            StageCapability::Speech,
            StageCapability::Subtitle,
        ])
    }

    async fn health(&self) -> ComponentHealth
    {
        ComponentHealth {
            component: "stage-dry-run".to_owned(),
            ready: true,
            detail: "actions are recorded without external side effects".to_owned(),
        }
    }

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>
    {
        action.validate()?;
        if self.actions.len() >= self.capacity
        {
            return Err(AppError::unavailable("stage dry-run queue is full"));
        }
        self.actions.push_back(action);
        Ok(())
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        self.actions.clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[tokio::test]
    async fn dry_run_records_valid_actions_and_capabilities()
    {
        let mut stage = DryRunStage::new(4).expect("stage creates");
        stage
            .execute(StageAction::Expression {
                emotion: Emotion::Happy,
            })
            .await
            .expect("expression executes");
        assert!(stage.capabilities().contains(&StageCapability::Expression));
        assert_eq!(stage.actions().next().map(StageAction::kind), Some("expression"));
        assert!(stage.health().await.ready);
    }

    #[tokio::test]
    async fn dry_run_rejects_invalid_actions()
    {
        let mut stage = DryRunStage::new(2).expect("stage creates");
        let error = stage
            .execute(StageAction::Mouth { value: 2.0 })
            .await
            .expect_err("mouth is out of range");
        assert!(error.to_string().contains("mouth"));
        let error = stage
            .execute(StageAction::Speak {
                turn_id: TurnId::new(),
                text: String::new(),
                interruptible: true,
            })
            .await
            .expect_err("empty speech is invalid");
        assert!(error.to_string().contains("speak"));
    }

    #[tokio::test]
    async fn dry_run_queue_is_bounded_and_interruptible()
    {
        let mut stage = DryRunStage::new(1).expect("stage creates");
        stage
            .execute(StageAction::Stop)
            .await
            .expect("stop executes");
        assert!(stage.execute(StageAction::Stop).await.is_err());
        stage.interrupt().await.expect("interrupt executes");
        assert!(stage.is_empty());
    }

    #[test]
    fn actions_round_trip_with_versioned_kind()
    {
        let action = StageAction::Subtitle {
            text: "hello".to_owned(),
            duration_ms: 1_000,
        };
        let encoded = serde_json::json!({
            "schema_version": STAGE_SCHEMA_VERSION,
            "action": action
        });
        let decoded: StageAction =
            serde_json::from_value(encoded["action"].clone()).expect("action parses");
        assert_eq!(decoded, action);
    }
}